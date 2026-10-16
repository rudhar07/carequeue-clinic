"""/api/doctors: the clinic's doctors, their working hours and slot grid."""
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Appointment, AppointmentStatus, Doctor
from app.schemas import DoctorCreate, DoctorDeleteResult, DoctorOut, DoctorUpdate, Slot, SlotGrid
from app.services.clock import clinic_now
from app.services.scheduling import slot_times

router = APIRouter(prefix="/api/doctors", tags=["doctors"])


def get_doctor_or_404(db: Session, doctor_id: int) -> Doctor:
    doctor = db.get(Doctor, doctor_id)
    if doctor is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Doctor not found")
    return doctor


@router.get("", response_model=list[DoctorOut])
def list_doctors(
    active_only: bool = False,
    specialty: str | None = None,
    db: Session = Depends(get_db),
):
    query = select(Doctor).order_by(Doctor.specialty, Doctor.full_name)
    if active_only:
        query = query.where(Doctor.is_active.is_(True))
    if specialty:
        query = query.where(Doctor.specialty == specialty)
    return db.scalars(query).all()


@router.post("", response_model=DoctorOut, status_code=status.HTTP_201_CREATED)
def create_doctor(body: DoctorCreate, db: Session = Depends(get_db)):
    doctor = Doctor(**body.model_dump(), is_active=True)
    db.add(doctor)
    db.commit()
    return doctor


@router.get("/{doctor_id}", response_model=DoctorOut)
def get_doctor(doctor_id: int, db: Session = Depends(get_db)):
    return get_doctor_or_404(db, doctor_id)


@router.put("/{doctor_id}", response_model=DoctorOut)
def update_doctor(doctor_id: int, body: DoctorUpdate, db: Session = Depends(get_db)):
    doctor = get_doctor_or_404(db, doctor_id)
    for field, value in body.model_dump().items():
        setattr(doctor, field, value)
    db.commit()
    return doctor


@router.delete("/{doctor_id}", response_model=DoctorDeleteResult)
def delete_doctor(doctor_id: int, db: Session = Depends(get_db)):
    """Hard delete a doctor with no history; otherwise only deactivate (keeps records)."""
    doctor = get_doctor_or_404(db, doctor_id)
    has_history = db.scalar(select(Appointment.id).where(Appointment.doctor_id == doctor_id).limit(1))
    if has_history is not None:
        doctor.is_active = False
        db.commit()
        return DoctorDeleteResult(id=doctor_id, action="deactivated")
    db.delete(doctor)
    db.commit()
    return DoctorDeleteResult(id=doctor_id, action="deleted")


@router.get("/{doctor_id}/slots", response_model=SlotGrid)
def doctor_slots(
    doctor_id: int,
    on: date = Query(alias="date"),
    db: Session = Depends(get_db),
    now: datetime = Depends(clinic_now),
):
    """Every slot of the day, marked free, booked (with its token) or past."""
    doctor = get_doctor_or_404(db, doctor_id)
    taken = dict(
        db.execute(
            select(Appointment.slot_time, Appointment.token_number).where(
                Appointment.doctor_id == doctor_id,
                Appointment.appointment_date == on,
                Appointment.status != AppointmentStatus.CANCELLED.value,
            )
        ).all()
    )
    slots = []
    for at in slot_times(doctor):
        if at in taken:
            slots.append(Slot(time=at, status="booked", token_number=taken[at]))
        elif datetime.combine(on, at) <= now:
            slots.append(Slot(time=at, status="past"))
        else:
            slots.append(Slot(time=at, status="free"))
    return SlotGrid(
        doctor_id=doctor_id,
        date=on,
        slot_minutes=doctor.slot_minutes,
        free_count=sum(slot.status == "free" for slot in slots),
        slots=slots,
    )
