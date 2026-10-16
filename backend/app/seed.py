"""Idempotent demo data: `python -m app.seed [--demo-queue]`.

* Doctors are matched by name and patients by phone, so running it twice adds nothing.
* `--demo-queue` also fills today's queue for each doctor (some visits done, one in
  consultation, a few waiting). Those rows are written directly, as if they had been
  booked earlier in the day, so the demo works at any time of day. Skipped for a
  doctor that already has appointments today.

All names and phone numbers are made up for the demo.
"""
import argparse
import logging
from datetime import date, time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import SessionLocal
from app.logging_config import configure_logging
from app.models import Appointment, AppointmentStatus, Doctor, Patient
from app.services.clock import clinic_now
from app.services.scheduling import slot_times

log = logging.getLogger("carequeue.seed")

DOCTORS = [
    # name, specialty, room, slot minutes, start, end
    ("Dr. Ananya Iyer", "General Medicine", "101", 15, time(9, 0), time(17, 0)),
    ("Dr. Rohan Mehta", "Pediatrics", "104", 20, time(10, 0), time(16, 0)),
    ("Dr. Kavya Reddy", "Dermatology", "201", 15, time(11, 0), time(18, 0)),
    ("Dr. Arjun Singh", "Orthopedics", "203", 30, time(9, 0), time(14, 0)),
]

PATIENTS = [
    # name, phone (fake), date of birth, gender
    ("Priya Sharma", "9876500001", date(1991, 4, 12), "female"),
    ("Rahul Verma", "9876500002", date(1985, 11, 3), "male"),
    ("Sneha Patil", "9876500003", date(2016, 7, 21), "female"),
    ("Vikram Nair", "9876500004", date(1972, 1, 30), "male"),
    ("Aisha Khan", "9876500005", date(1998, 9, 8), "female"),
    ("Karthik Subramanian", "9876500006", date(1964, 5, 17), "male"),
    ("Meera Joshi", "9876500007", date(2019, 2, 14), "female"),
    ("Sameer Gupta", "9876500008", date(1989, 12, 25), "male"),
    ("Divya Menon", "9876500009", date(2001, 6, 2), "female"),
    ("Aditya Rao", "9876500010", date(1995, 3, 19), "male"),
    ("Neha Bansal", "9876500011", date(1979, 8, 27), "female"),
    ("Ishaan Chatterjee", "9876500012", date(2012, 10, 5), "male"),
]

# Typical reasons for a visit, per specialty (used for the demo queue).
REASONS = {
    "General Medicine": ["Fever and sore throat for 3 days", "Follow-up on blood pressure",
                         "Persistent cough", "Annual health check-up", "Diabetes review"],
    "Pediatrics": ["Routine vaccination", "Fever and cold", "Growth check-up", "Ear pain"],
    "Dermatology": ["Skin rash on forearm", "Acne follow-up", "Itchy scalp", "Mole check"],
    "Orthopedics": ["Knee pain after running", "Lower back pain", "Shoulder stiffness", "Ankle sprain review"],
}

# Status of the first N tokens in each doctor's demo queue; the rest stay booked.
DEMO_STATUSES = [
    AppointmentStatus.COMPLETED,
    AppointmentStatus.COMPLETED,
    AppointmentStatus.NO_SHOW,
    AppointmentStatus.IN_CONSULTATION,
    AppointmentStatus.CHECKED_IN,
    AppointmentStatus.CHECKED_IN,
    AppointmentStatus.CHECKED_IN,
    AppointmentStatus.BOOKED,
    AppointmentStatus.BOOKED,
]


def seed_reference_data(db: Session) -> tuple[int, int]:
    """Insert missing doctors and patients. Returns how many of each were added."""
    added_doctors = added_patients = 0
    for name, specialty, room, minutes, start, end in DOCTORS:
        if db.scalar(select(Doctor.id).where(Doctor.full_name == name)) is None:
            db.add(Doctor(full_name=name, specialty=specialty, room=room, slot_minutes=minutes,
                          start_time=start, end_time=end, is_active=True))
            added_doctors += 1
    for name, phone, dob, gender in PATIENTS:
        if db.scalar(select(Patient.id).where(Patient.phone == phone)) is None:
            db.add(Patient(full_name=name, phone=phone, date_of_birth=dob, gender=gender))
            added_patients += 1
    db.commit()
    return added_doctors, added_patients


def seed_demo_queue(db: Session, today: date) -> int:
    """Fill today's queue for every active doctor that has no appointments today."""
    patients = db.scalars(select(Patient).order_by(Patient.id)).all()
    doctors = db.scalars(select(Doctor).where(Doctor.is_active.is_(True)).order_by(Doctor.id)).all()
    added = 0
    for d_index, doctor in enumerate(doctors):
        exists = db.scalar(
            select(Appointment.id).where(Appointment.doctor_id == doctor.id, Appointment.appointment_date == today)
        )
        if exists is not None:
            continue
        slots = slot_times(doctor)
        reasons = REASONS.get(doctor.specialty, REASONS["General Medicine"])
        # Fewer patients for the later doctors so the queues look different.
        for token, status in enumerate(DEMO_STATUSES[: len(DEMO_STATUSES) - d_index], start=1):
            patient = patients[(d_index * 3 + token) % len(patients)]
            db.add(Appointment(
                patient=patient, doctor=doctor, appointment_date=today, slot_time=slots[token - 1],
                reason=reasons[token % len(reasons)], token_number=token, status=status.value,
            ))
            added += 1
    db.commit()
    return added


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--demo-queue", action="store_true", help="also fill today's queue")
    args = parser.parse_args()
    configure_logging(get_settings().log_level)
    with SessionLocal() as db:
        doctors, patients = seed_reference_data(db)
        queue = seed_demo_queue(db, clinic_now().date()) if args.demo_queue else 0
    log.info("seed finished", extra={"doctors_added": doctors, "patients_added": patients, "appointments_added": queue})


if __name__ == "__main__":
    main()
