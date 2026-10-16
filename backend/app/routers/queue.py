"""/api/queue and /api/stats: the live waiting-room view of today."""
from datetime import date, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.db import get_db
from app.metrics import refresh_all_queue_gauges, refresh_queue_gauge
from app.models import Appointment, AppointmentStatus, Doctor, Patient
from app.routers.doctors import get_doctor_or_404
from app.schemas import QueueOut, TodayStats
from app.services.clock import clinic_now

router = APIRouter(prefix="/api", tags=["queue"])
S = AppointmentStatus


@router.get("/queue", response_model=QueueOut)
def doctor_queue(
    doctor_id: int,
    on: date | None = Query(default=None, alias="date"),
    db: Session = Depends(get_db),
    now: datetime = Depends(clinic_now),
):
    """Queue for one doctor and day (default today), ordered by token number."""
    doctor: Doctor = get_doctor_or_404(db, doctor_id)
    day = on or now.date()
    appts = db.scalars(
        select(Appointment)
        .options(joinedload(Appointment.patient), joinedload(Appointment.doctor))
        .where(Appointment.doctor_id == doctor_id, Appointment.appointment_date == day)
        .order_by(Appointment.token_number)
    ).all()

    def having(*statuses: S) -> list[Appointment]:
        return [a for a in appts if a.status in {s.value for s in statuses}]

    serving = having(S.IN_CONSULTATION)
    waiting = having(S.CHECKED_IN)
    if day == now.date():
        refresh_queue_gauge(db, doctor, day)
    return QueueOut(
        doctor=doctor,
        date=day,
        now_serving=serving[0] if serving else None,
        next_up=waiting[0] if waiting else None,
        waiting_count=len(waiting),
        waiting=waiting,
        not_arrived=having(S.BOOKED),
        done=having(S.COMPLETED, S.NO_SHOW, S.CANCELLED),
    )


@router.get("/stats/today", response_model=TodayStats)
def today_stats(db: Session = Depends(get_db), now: datetime = Depends(clinic_now)):
    """Counts for the UI header. Also refreshes the per-doctor waiting gauges,
    since every open CareQueue screen polls this endpoint."""
    today = now.date()
    refresh_all_queue_gauges(db, today)
    counts = dict(
        db.execute(
            select(Appointment.status, func.count(Appointment.id))
            .where(Appointment.appointment_date == today)
            .group_by(Appointment.status)
        ).all()
    )
    by_status = {s.value: counts.get(s.value, 0) for s in S}
    return TodayStats(
        date=today,
        total=sum(by_status.values()),
        by_status=by_status,
        active_doctors=db.scalar(select(func.count(Doctor.id)).where(Doctor.is_active.is_(True))) or 0,
        patients=db.scalar(select(func.count(Patient.id))) or 0,
    )
