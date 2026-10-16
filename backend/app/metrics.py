"""Prometheus metrics: HTTP metrics from the instrumentator plus clinic business metrics.

Run one Uvicorn worker per container (scale with replicas) so every scrape sees
the whole process's counters.
"""
from datetime import date

from fastapi import FastAPI
from prometheus_client import Counter, Gauge
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Appointment, AppointmentStatus, Doctor

APPOINTMENTS_BOOKED = Counter(
    "carequeue_appointments_booked_total",
    "Appointments booked through the API",
)
APPOINTMENT_STATUS = Counter(
    "carequeue_appointments_status_total",
    "Appointment status changes, by the new status",
    ["status"],
)
QUEUE_WAITING = Gauge(
    "carequeue_queue_waiting",
    "Checked-in patients waiting to be called in today, per doctor",
    ["doctor"],
)


def setup_metrics(app: FastAPI) -> None:
    """Request count, latency histogram and status codes at GET /metrics."""
    Instrumentator(
        should_group_status_codes=False,
        excluded_handlers=["/metrics", "/health", "/ready"],
    ).instrument(app).expose(app, include_in_schema=False)


def refresh_queue_gauge(db: Session, doctor: Doctor, today: date) -> int:
    """Recount the waiting patients for one doctor and publish the gauge."""
    waiting = db.scalar(
        select(func.count(Appointment.id)).where(
            Appointment.doctor_id == doctor.id,
            Appointment.appointment_date == today,
            Appointment.status == AppointmentStatus.CHECKED_IN.value,
        )
    ) or 0
    QUEUE_WAITING.labels(doctor=doctor.full_name).set(waiting)
    return waiting


def refresh_all_queue_gauges(db: Session, today: date) -> None:
    """Publish the waiting count of every active doctor in one grouped query."""
    counts = dict(
        db.execute(
            select(Appointment.doctor_id, func.count(Appointment.id))
            .where(
                Appointment.appointment_date == today,
                Appointment.status == AppointmentStatus.CHECKED_IN.value,
            )
            .group_by(Appointment.doctor_id)
        ).all()
    )
    for doctor in db.scalars(select(Doctor).where(Doctor.is_active.is_(True))):
        QUEUE_WAITING.labels(doctor=doctor.full_name).set(counts.get(doctor.id, 0))
