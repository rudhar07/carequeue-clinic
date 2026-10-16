"""ORM models: doctors, patients and the appointments that link them."""
from datetime import date, datetime, time, timezone
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Time,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Gender(StrEnum):
    FEMALE = "female"
    MALE = "male"
    OTHER = "other"


class AppointmentStatus(StrEnum):
    BOOKED = "booked"
    CHECKED_IN = "checked_in"
    IN_CONSULTATION = "in_consultation"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


# Used by the CHECK constraints below and by the migration.
GENDER_VALUES = tuple(g.value for g in Gender)
STATUS_VALUES = tuple(s.value for s in AppointmentStatus)


class Doctor(Base):
    __tablename__ = "doctors"
    __table_args__ = (
        CheckConstraint("start_time < end_time", name="ck_doctors_hours"),
        CheckConstraint("slot_minutes BETWEEN 5 AND 120", name="ck_doctors_slot_minutes"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(120))
    specialty: Mapped[str] = mapped_column(String(80), index=True)
    room: Mapped[str] = mapped_column(String(20))
    slot_minutes: Mapped[int] = mapped_column(Integer, default=15)
    start_time: Mapped[time] = mapped_column(Time, default=time(9, 0))
    end_time: Mapped[time] = mapped_column(Time, default=time(17, 0))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))

    appointments: Mapped[list["Appointment"]] = relationship(back_populates="doctor")


class Patient(Base):
    __tablename__ = "patients"
    __table_args__ = (
        CheckConstraint(f"gender IN {GENDER_VALUES}", name="ck_patients_gender"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(120), index=True)
    # Stored normalised as 10 digits (no +91), unique per patient.
    phone: Mapped[str] = mapped_column(String(10), unique=True)
    date_of_birth: Mapped[date] = mapped_column(Date)
    gender: Mapped[str] = mapped_column(String(10))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    appointments: Mapped[list["Appointment"]] = relationship(
        back_populates="patient", cascade="all, delete-orphan"
    )


class Appointment(Base):
    __tablename__ = "appointments"
    __table_args__ = (
        CheckConstraint(f"status IN {STATUS_VALUES}", name="ck_appointments_status"),
        # No double booking: one live (non-cancelled) appointment per doctor/date/slot.
        # A partial unique index works in both PostgreSQL and SQLite.
        Index(
            "uq_appointments_active_slot",
            "doctor_id",
            "appointment_date",
            "slot_time",
            unique=True,
            postgresql_where=text("status <> 'cancelled'"),
            sqlite_where=text("status <> 'cancelled'"),
        ),
        # Token numbers never repeat for a doctor on a given day.
        Index("uq_appointments_token", "doctor_id", "appointment_date", "token_number", unique=True),
        # The queue and the "today" stats both filter on date first.
        Index("ix_appointments_date_status", "appointment_date", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id", ondelete="CASCADE"), index=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id", ondelete="RESTRICT"))
    appointment_date: Mapped[date] = mapped_column(Date)
    slot_time: Mapped[time] = mapped_column(Time)
    reason: Mapped[str] = mapped_column(Text, default="")
    token_number: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default=AppointmentStatus.BOOKED.value)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    patient: Mapped[Patient] = relationship(back_populates="appointments")
    doctor: Mapped[Doctor] = relationship(back_populates="appointments")
