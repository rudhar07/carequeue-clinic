"""Pydantic v2 request/response models and their validation rules."""
import re
from datetime import date, datetime, time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models import AppointmentStatus, Gender

# Indian mobile numbers: 10 digits starting with 6, 7, 8 or 9.
INDIAN_MOBILE = re.compile(r"^[6-9]\d{9}$")


def normalise_phone(raw: str) -> str:
    """Accept '98765 43210', '+91-9876543210' or '09876543210'; return '9876543210'."""
    digits = re.sub(r"[\s\-()]", "", raw)
    if digits.startswith("+91"):
        digits = digits[3:]
    elif digits.startswith("91") and len(digits) == 12:
        digits = digits[2:]
    elif digits.startswith("0") and len(digits) == 11:
        digits = digits[1:]
    if not INDIAN_MOBILE.match(digits):
        raise ValueError("phone must be a 10-digit Indian mobile number starting with 6-9")
    return digits


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------- doctors ----------

class DoctorBase(BaseModel):
    full_name: str = Field(min_length=3, max_length=120)
    specialty: str = Field(min_length=2, max_length=80)
    room: str = Field(min_length=1, max_length=20)
    slot_minutes: int = Field(default=15, ge=5, le=120)
    start_time: time = time(9, 0)
    end_time: time = time(17, 0)

    @model_validator(mode="after")
    def check_hours(self):
        if self.start_time >= self.end_time:
            raise ValueError("start_time must be before end_time")
        return self


class DoctorCreate(DoctorBase):
    pass


class DoctorUpdate(DoctorBase):
    is_active: bool = True


class DoctorOut(ORMModel):
    id: int
    full_name: str
    specialty: str
    room: str
    slot_minutes: int
    start_time: time
    end_time: time
    is_active: bool


class DoctorDeleteResult(BaseModel):
    id: int
    action: Literal["deleted", "deactivated"]


class Slot(BaseModel):
    time: time
    status: Literal["free", "booked", "past"]
    token_number: int | None = None


class SlotGrid(BaseModel):
    doctor_id: int
    date: date
    slot_minutes: int
    free_count: int
    slots: list[Slot]


# ---------- patients ----------

class PatientBase(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    phone: str
    date_of_birth: date
    gender: Gender

    @field_validator("full_name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        value = " ".join(value.split())
        if len(value) < 2:
            raise ValueError("full_name is too short")
        return value

    @field_validator("phone")
    @classmethod
    def valid_phone(cls, value: str) -> str:
        return normalise_phone(value)

    @field_validator("date_of_birth")
    @classmethod
    def plausible_dob(cls, value: date) -> date:
        today = date.today()
        if value > today:
            raise ValueError("date_of_birth cannot be in the future")
        if today.year - value.year > 120:
            raise ValueError("date_of_birth is more than 120 years ago")
        return value


class PatientCreate(PatientBase):
    pass


class PatientUpdate(PatientBase):
    pass


class PatientOut(ORMModel):
    id: int
    full_name: str
    phone: str
    date_of_birth: date
    gender: Gender
    created_at: datetime


# ---------- appointments ----------

class AppointmentCreate(BaseModel):
    patient_id: int = Field(gt=0)
    doctor_id: int = Field(gt=0)
    appointment_date: date
    slot_time: time
    reason: str = Field(default="", max_length=500)


class AppointmentUpdate(BaseModel):
    """Reschedule (doctor/date/slot) or edit the reason of a booked appointment."""

    doctor_id: int = Field(gt=0)
    appointment_date: date
    slot_time: time
    reason: str = Field(default="", max_length=500)


class StatusChange(BaseModel):
    status: AppointmentStatus


class PersonRef(ORMModel):
    id: int
    full_name: str


class DoctorRef(PersonRef):
    specialty: str
    room: str


class PatientRef(PersonRef):
    phone: str


class AppointmentOut(ORMModel):
    id: int
    patient_id: int
    doctor_id: int
    appointment_date: date
    slot_time: time
    reason: str
    token_number: int
    status: AppointmentStatus
    created_at: datetime
    updated_at: datetime
    patient: PatientRef
    doctor: DoctorRef


# ---------- queue and stats ----------

class QueueOut(BaseModel):
    doctor: DoctorRef
    date: date
    now_serving: AppointmentOut | None
    next_up: AppointmentOut | None
    waiting_count: int
    waiting: list[AppointmentOut]
    not_arrived: list[AppointmentOut]
    done: list[AppointmentOut]


class TodayStats(BaseModel):
    date: date
    total: int
    by_status: dict[str, int]
    active_doctors: int
    patients: int
