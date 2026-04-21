from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.routes import router as api_router
from app.core.config import settings
from app.db.init_db import init_db
from app.ui.routes import router as ui_router


BASE_DIR = Path(__file__).resolve().parent.parent


def _resolve_local_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return BASE_DIR / path


static_dir = BASE_DIR / "app" / "static"
static_dir.mkdir(parents=True, exist_ok=True)
upload_dir = _resolve_local_path(settings.local_upload_dir)
upload_dir.mkdir(parents=True, exist_ok=True)

app = FastAPI(title=settings.app_name)
app.include_router(api_router, prefix=settings.api_prefix)
app.include_router(ui_router)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
app.mount("/uploads", StaticFiles(directory=str(upload_dir)), name="uploads")


@app.on_event("startup")
def startup() -> None:
    init_db()
    upload_dir.mkdir(parents=True, exist_ok=True)


@app.get("/health")
def health():
    return {"status": "ok"}
