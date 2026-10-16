"""/api/appointments: booking, rescheduling and the visit status workflow."""
import logging
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.db import get_db
from app.metrics import APPOINTMENT_STATUS, APPOINTMENTS_BOOKED, refresh_queue_gauge
from app.models import Appointment, AppointmentStatus, Doctor, Patient
from app.routers.doctors import get_doctor_or_404
from app.routers.patients import get_patient_or_404
from app.schemas import AppointmentCreate, AppointmentOut, AppointmentUpdate, StatusChange
from app.services.clock import clinic_now
from app.services.scheduling import check_transition, ensure_slot_free, next_token, validate_slot

router = APIRouter(prefix="/api/appointments", tags=["appointments"])
log = logging.getLogger("carequeue.appointments")


def get_appointment_or_404(db: Session, appointment_id: int) -> Appointment:
    appt = db.scalar(
        select(Appointment)
        .options(joinedload(Appointment.patient), joinedload(Appointment.doctor))
        .where(Appointment.id == appointment_id)
    )
    if appt is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Appointment not found")
    return appt


def _commit_booking(db: Session) -> None:
    """The partial unique index catches a race between two simultaneous bookings."""
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "This slot is already booked") from None


@router.get("", response_model=list[AppointmentOut])
def list_appointments(
    on: date | None = Query(default=None, alias="date"),
    doctor_id: int | None = None,
    patient_id: int | None = None,
    status_: AppointmentStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    query = (
        select(Appointment)
        .options(joinedload(Appointment.patient), joinedload(Appointment.doctor))
        .order_by(Appointment.appointment_date, Appointment.slot_time, Appointment.doctor_id)
        .limit(limit)
    )
    if on is not None:
        query = query.where(Appointment.appointment_date == on)
    if doctor_id is not None:
        query = query.where(Appointment.doctor_id == doctor_id)
    if patient_id is not None:
        query = query.where(Appointment.patient_id == patient_id)
    if status_ is not None:
        query = query.where(Appointment.status == status_.value)
    return db.scalars(query).all()


@router.post("", response_model=AppointmentOut, status_code=status.HTTP_201_CREATED)
def book_appointment(
    body: AppointmentCreate,
    db: Session = Depends(get_db),
    now: datetime = Depends(clinic_now),
):
    patient: Patient = get_patient_or_404(db, body.patient_id)
    doctor: Doctor = get_doctor_or_404(db, body.doctor_id)
    validate_slot(doctor, body.appointment_date, body.slot_time, now)
    ensure_slot_free(db, doctor.id, body.appointment_date, body.slot_time)

    appt = Appointment(
        patient=patient,
        doctor=doctor,
        appointment_date=body.appointment_date,
        slot_time=body.slot_time,
        reason=body.reason.strip(),
        token_number=next_token(db, doctor.id, body.appointment_date),
        status=AppointmentStatus.BOOKED.value,
    )
    db.add(appt)
    _commit_booking(db)
    APPOINTMENTS_BOOKED.inc()
    APPOINTMENT_STATUS.labels(status=AppointmentStatus.BOOKED.value).inc()
    log.info(
        "appointment booked",
        extra={"appointment_id": appt.id, "doctor_id": doctor.id, "token": appt.token_number},
    )
    return appt


@router.get("/{appointment_id}", response_model=AppointmentOut)
def get_appointment(appointment_id: int, db: Session = Depends(get_db)):
    return get_appointment_or_404(db, appointment_id)


@router.put("/{appointment_id}", response_model=AppointmentOut)
def reschedule_appointment(
    appointment_id: int,
    body: AppointmentUpdate,
    db: Session = Depends(get_db),
    now: datetime = Depends(clinic_now),
):
    """Only a booked (not yet arrived) appointment can be moved or edited."""
    appt = get_appointment_or_404(db, appointment_id)
    if appt.status != AppointmentStatus.BOOKED.value:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Cannot edit an appointment that is {appt.status}")

    moved = (body.doctor_id, body.appointment_date, body.slot_time) != (
        appt.doctor_id,
        appt.appointment_date,
        appt.slot_time,
    )
    if moved:
        doctor = get_doctor_or_404(db, body.doctor_id)
        validate_slot(doctor, body.appointment_date, body.slot_time, now)
        ensure_slot_free(db, doctor.id, body.appointment_date, body.slot_time, ignore_id=appt.id)
        if (doctor.id, body.appointment_date) != (appt.doctor_id, appt.appointment_date):
            appt.token_number = next_token(db, doctor.id, body.appointment_date)
        appt.doctor = doctor
        appt.appointment_date = body.appointment_date
        appt.slot_time = body.slot_time
    appt.reason = body.reason.strip()
    _commit_booking(db)
    return appt


@router.patch("/{appointment_id}/status", response_model=AppointmentOut)
def change_status(
    appointment_id: int,
    body: StatusChange,
    db: Session = Depends(get_db),
    now: datetime = Depends(clinic_now),
):
    appt = get_appointment_or_404(db, appointment_id)
    old = appt.status
    check_transition(db, appt, body.status, now.date())
    appt.status = body.status.value
    db.commit()
    APPOINTMENT_STATUS.labels(status=body.status.value).inc()
    if appt.appointment_date == now.date():
        refresh_queue_gauge(db, appt.doctor, now.date())
    log.info(
        "appointment status changed",
        extra={"appointment_id": appt.id, "from": old, "to": appt.status},
    )
    return appt


@router.delete("/{appointment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_appointment(appointment_id: int, db: Session = Depends(get_db)):
    """Visits that happened (in consultation / completed) are medical records and stay."""
    appt = get_appointment_or_404(db, appointment_id)
    if appt.status in (AppointmentStatus.IN_CONSULTATION.value, AppointmentStatus.COMPLETED.value):
        raise HTTPException(status.HTTP_409_CONFLICT, f"Cannot delete an appointment that is {appt.status}")
    db.delete(appt)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
