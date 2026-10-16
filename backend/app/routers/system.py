"""Probes and build info: /health (liveness), /ready (readiness), /api/info."""
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db

router = APIRouter(tags=["system"])


@router.get("/health")
def health():
    """Liveness: the process is up. Never touches the database."""
    return {"status": "ok"}


@router.get("/ready")
def ready(db: Session = Depends(get_db)):
    """Readiness: only accept traffic when the database answers."""
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return JSONResponse(status_code=503, content={"status": "unavailable", "database": "down"})
    return {"status": "ready", "database": "up"}


@router.get("/api/info")
def info():
    settings = get_settings()
    return {"app": settings.app_name, "version": settings.app_version, "commit": settings.git_sha}
