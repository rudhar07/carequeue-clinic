"""CareQueue API: clinic appointments and the live patient queue."""
import logging
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.logging_config import configure_logging
from app.metrics import setup_metrics
from app.routers import appointments, doctors, patients, queue, system

settings = get_settings()
configure_logging(settings.log_level)
log = logging.getLogger("carequeue.http")

app = FastAPI(
    title="CareQueue API",
    description="Clinic appointments & patient queue",
    version=settings.app_version,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """One structured access-log line per request (probes and scrapes are skipped)."""
    started = time.perf_counter()
    response = await call_next(request)
    if request.url.path not in ("/health", "/ready", "/metrics"):
        log.info(
            "request",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": round((time.perf_counter() - started) * 1000, 2),
            },
        )
    return response


for module in (system, doctors, patients, appointments, queue):
    app.include_router(module.router)

setup_metrics(app)
