from fastapi import FastAPI

from app.api.routes import router as api_router
from app.core.config import settings


app = FastAPI(title=settings.app_name)
app.include_router(api_router, prefix=settings.api_prefix)


@app.get("/health")
def health():
    return {"status": "ok"}
