"""Business rules for the slot grid, bookings and appointment status changes."""
from datetime import date, datetime, time, timedelta

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Appointment, AppointmentStatus, Doctor

S = AppointmentStatus

# Allowed status changes. Anything not listed is rejected with 409.
TRANSITIONS: dict[S, set[S]] = {
    S.BOOKED: {S.CHECKED_IN, S.CANCELLED, S.NO_SHOW},
    S.CHECKED_IN: {S.IN_CONSULTATION, S.CANCELLED, S.NO_SHOW},
    S.IN_CONSULTATION: {S.COMPLETED},
    S.COMPLETED: set(),
    S.CANCELLED: set(),
    S.NO_SHOW: set(),
}

# Statuses that still hold the slot / are part of the live queue.
ACTIVE_STATUSES = (S.BOOKED, S.CHECKED_IN, S.IN_CONSULTATION)


def slot_times(doctor: Doctor) -> list[time]:
    """All slot start times between the doctor's start and end time."""
    day = date(2000, 1, 1)  # any date: only the time part matters
    cursor = datetime.combine(day, doctor.start_time)
    end = datetime.combine(day, doctor.end_time)
    step = timedelta(minutes=doctor.slot_minutes)
    slots = []
    while cursor + step <= end:
        slots.append(cursor.time())
        cursor += step
    return slots


def validate_slot(doctor: Doctor, on: date, at: time, now: datetime) -> None:
    """Raise if the doctor cannot take a booking at this date/time."""
    if not doctor.is_active:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Dr. {doctor.full_name} is not taking appointments")
    if at not in slot_times(doctor):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"{at.strftime('%H:%M')} is not a valid slot for this doctor "
            f"({doctor.start_time:%H:%M}-{doctor.end_time:%H:%M}, every {doctor.slot_minutes} min)",
        )
    if datetime.combine(on, at) <= now:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Cannot book a slot in the past")


def ensure_slot_free(db: Session, doctor_id: int, on: date, at: time, ignore_id: int | None = None) -> None:
    """Code-level double-booking check (the partial unique index is the backstop)."""
    query = select(Appointment.id).where(
        Appointment.doctor_id == doctor_id,
        Appointment.appointment_date == on,
        Appointment.slot_time == at,
        Appointment.status != S.CANCELLED.value,
    )
    if ignore_id is not None:
        query = query.where(Appointment.id != ignore_id)
    if db.scalar(query) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "This slot is already booked")


def next_token(db: Session, doctor_id: int, on: date) -> int:
    """Tokens are sequential per doctor per day and are never reused."""
    current = db.scalar(
        select(func.max(Appointment.token_number)).where(
            Appointment.doctor_id == doctor_id, Appointment.appointment_date == on
        )
    )
    return (current or 0) + 1


def check_transition(db: Session, appt: Appointment, new: S, today: date) -> None:
    """Validate a status change; raises 409 when it is not allowed."""
    old = S(appt.status)
    if new not in TRANSITIONS[old]:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Cannot change status from {old} to {new}")
    if new in (S.CHECKED_IN, S.IN_CONSULTATION) and appt.appointment_date != today:
        raise HTTPException(status.HTTP_409_CONFLICT, "Patients can only check in / be called in on the appointment day")
    if new == S.IN_CONSULTATION:
        busy = db.scalar(
            select(Appointment.token_number).where(
                Appointment.doctor_id == appt.doctor_id,
                Appointment.appointment_date == appt.appointment_date,
                Appointment.status == S.IN_CONSULTATION.value,
            )
        )
        if busy is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, f"The doctor is still with token #{busy}")
