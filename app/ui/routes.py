import re
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.api.routes import create_report, hash_plate
from app.core.config import settings
from app.core.security import require_admin
from app.db.models import BehaviorCategory, DriverRiskProfiles, Reports, Users, VerificationStatus
from app.db.session import get_db
from app.schemas import ReportCreate
from app.workers.tasks import recompute_risk_profile_task


SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]+")
BASE_DIR = Path(__file__).resolve().parents[2]
templates = Jinja2Templates(directory=str(BASE_DIR / "app" / "templates"))
router = APIRouter()


def _resolve_local_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return BASE_DIR / path


def _sanitize_filename(filename: str) -> str:
    safe_name = SAFE_FILENAME_RE.sub("_", Path(filename).name.strip())
    if not safe_name or safe_name in {".", ".."}:
        raise ValueError("Invalid filename")
    return safe_name[:128]


def _report_form_context(db: Session) -> dict:
    reporters = db.execute(select(Users).order_by(desc(Users.created_at)).limit(25)).scalars().all()
    return {"reporters": reporters, "behavior_categories": [item.value for item in BehaviorCategory]}


def _dashboard_context(db: Session) -> dict:
    pending_count = db.execute(
        select(func.count(Reports.id)).where(Reports.verification_status == VerificationStatus.pending)
    ).scalar_one()
    verified_count = db.execute(
        select(func.count(Reports.id)).where(Reports.verification_status == VerificationStatus.verified)
    ).scalar_one()
    quarantined_count = db.execute(
        select(func.count(Reports.id)).where(Reports.verification_status == VerificationStatus.quarantined)
    ).scalar_one()
    reports = (
        db.execute(select(Reports).order_by(desc(Reports.timestamp)).limit(settings.admin_page_size))
        .scalars()
        .all()
    )
    users = db.execute(select(Users).order_by(desc(Users.created_at)).limit(settings.admin_page_size)).scalars().all()
    profiles = (
        db.execute(
            select(DriverRiskProfiles).order_by(desc(DriverRiskProfiles.last_calculated_at)).limit(
                settings.admin_page_size
            )
        )
        .scalars()
        .all()
    )
    return {
        "pending_count": pending_count,
        "verified_count": verified_count,
        "quarantined_count": quarantined_count,
        "reports": reports,
        "users": users,
        "profiles": profiles,
    }


def _parse_reporter_id(value: str) -> UUID:
    try:
        return UUID(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="reporter_id must be a valid UUID") from exc


@router.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@router.get("/ui/report", response_class=HTMLResponse)
def report_form(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse("user_report.html", {"request": request, **_report_form_context(db)})


@router.post("/ui/report", response_class=HTMLResponse)
async def submit_report_form(
    request: Request,
    db: Session = Depends(get_db),
    reporter_id: str = Form(default=""),
    social_graph_verified: bool = Form(default=False),
    target_license_plate: str = Form(...),
    behavior_category: BehaviorCategory = Form(...),
    latitude: float = Form(...),
    longitude: float = Form(...),
    reporter_latitude: float = Form(...),
    reporter_longitude: float = Form(...),
    media_file: UploadFile | None = File(default=None),
):
    try:
        media_url: str | None = None
        if media_file and media_file.filename:
            if media_file.content_type not in settings.allowed_media_content_types:
                raise HTTPException(status_code=400, detail="Unsupported media content type")
            payload = await media_file.read()
            if len(payload) > settings.max_upload_bytes:
                raise HTTPException(status_code=413, detail="Uploaded media is too large")
            upload_dir = _resolve_local_path(settings.local_upload_dir)
            upload_dir.mkdir(parents=True, exist_ok=True)
            safe_name = _sanitize_filename(media_file.filename)
            local_name = f"{uuid4()}-{safe_name}"
            (upload_dir / local_name).write_bytes(payload)
            media_url = f"/uploads/{local_name}"

        if reporter_id.strip():
            selected_reporter_id = _parse_reporter_id(reporter_id.strip())
            reporter = db.get(Users, selected_reporter_id)
            if reporter is None:
                raise HTTPException(status_code=404, detail="Reporter not found")
        else:
            reporter = Users(social_graph_verified=social_graph_verified)
            db.add(reporter)
            db.commit()
            db.refresh(reporter)

        report_payload = ReportCreate(
            reporter_id=reporter.id,
            target_license_plate=target_license_plate,
            behavior_category=behavior_category,
            latitude=latitude,
            longitude=longitude,
            reporter_latitude=reporter_latitude,
            reporter_longitude=reporter_longitude,
            timestamp=datetime.now(timezone.utc),
            media_url=media_url,
        )
        response = create_report(report_payload, db)
    except HTTPException as exc:
        context = {"request": request, **_report_form_context(db), "submission_error": exc.detail}
        return templates.TemplateResponse("user_report.html", context, status_code=exc.status_code)
    except ValidationError as exc:
        context = {"request": request, **_report_form_context(db), "submission_error": exc.errors()}
        return templates.TemplateResponse("user_report.html", context, status_code=422)
    except ValueError as exc:
        context = {"request": request, **_report_form_context(db), "submission_error": str(exc)}
        return templates.TemplateResponse("user_report.html", context, status_code=400)

    plate_hash = hash_plate(target_license_plate)
    context = {
        "request": request,
        **_report_form_context(db),
        "submission_ok": True,
        "report_id": response.id,
        "verification_status": response.verification_status.value,
        "hashed_plate": plate_hash,
        "risk_profile_url": f"/api/v1/risk-profile/{plate_hash}",
    }
    return templates.TemplateResponse("user_report.html", context)


@router.get("/admin", response_class=HTMLResponse)
def admin_dashboard(
    request: Request,
    db: Session = Depends(get_db),
    _: str = Depends(require_admin),
):
    return templates.TemplateResponse("admin_dashboard.html", {"request": request, **_dashboard_context(db)})


@router.post("/admin/reports/{report_id}/status")
def update_report_status(
    report_id: UUID,
    verification_status: VerificationStatus = Form(...),
    db: Session = Depends(get_db),
    _: str = Depends(require_admin),
):
    report = db.get(Reports, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    report.verification_status = verification_status
    db.add(report)
    db.commit()
    recompute_risk_profile_task.delay(report.target_license_plate)
    return RedirectResponse(url="/admin", status_code=303)
