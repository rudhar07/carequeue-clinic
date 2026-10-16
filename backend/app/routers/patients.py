"""/api/patients: patient registry with name/phone search."""
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Appointment, Patient
from app.schemas import PatientCreate, PatientOut, PatientUpdate
from app.services.scheduling import ACTIVE_STATUSES

router = APIRouter(prefix="/api/patients", tags=["patients"])

DUPLICATE_PHONE = "A patient with this phone number already exists"


def get_patient_or_404(db: Session, patient_id: int) -> Patient:
    patient = db.get(Patient, patient_id)
    if patient is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Patient not found")
    return patient


def _phone_taken(db: Session, phone: str, ignore_id: int | None = None) -> bool:
    query = select(Patient.id).where(Patient.phone == phone)
    if ignore_id is not None:
        query = query.where(Patient.id != ignore_id)
    return db.scalar(query) is not None


def _commit_or_409(db: Session) -> None:
    """Two concurrent requests can both pass the check; the unique index decides."""
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, DUPLICATE_PHONE) from None


@router.get("", response_model=list[PatientOut])
def list_patients(
    q: str | None = Query(default=None, max_length=60, description="Name or phone fragment"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    query = select(Patient).order_by(Patient.full_name).limit(limit).offset(offset)
    if q and q.strip():
        term = q.strip()
        query = query.where(or_(Patient.full_name.ilike(f"%{term}%"), Patient.phone.contains(term)))
    return db.scalars(query).all()


@router.post("", response_model=PatientOut, status_code=status.HTTP_201_CREATED)
def create_patient(body: PatientCreate, db: Session = Depends(get_db)):
    if _phone_taken(db, body.phone):
        raise HTTPException(status.HTTP_409_CONFLICT, DUPLICATE_PHONE)
    patient = Patient(**body.model_dump())
    db.add(patient)
    _commit_or_409(db)
    return patient


@router.get("/{patient_id}", response_model=PatientOut)
def get_patient(patient_id: int, db: Session = Depends(get_db)):
    return get_patient_or_404(db, patient_id)


@router.put("/{patient_id}", response_model=PatientOut)
def update_patient(patient_id: int, body: PatientUpdate, db: Session = Depends(get_db)):
    patient = get_patient_or_404(db, patient_id)
    if _phone_taken(db, body.phone, ignore_id=patient_id):
        raise HTTPException(status.HTTP_409_CONFLICT, DUPLICATE_PHONE)
    for field, value in body.model_dump().items():
        setattr(patient, field, value)
    _commit_or_409(db)
    return patient


@router.delete("/{patient_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_patient(patient_id: int, db: Session = Depends(get_db)):
    """Refuse while the patient has an upcoming or ongoing visit; past visits are removed too."""
    patient = get_patient_or_404(db, patient_id)
    active = db.scalar(
        select(Appointment.id).where(
            Appointment.patient_id == patient_id,
            Appointment.status.in_([s.value for s in ACTIVE_STATUSES]),
        ).limit(1)
    )
    if active is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Patient has an active appointment; cancel it before deleting"
        )
    db.delete(patient)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
