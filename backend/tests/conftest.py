"""Test setup.

* Every test gets a fresh in-memory SQLite database (StaticPool = one shared
  connection), so the real PostgreSQL database is never touched.
* The clinic clock is pinned to a fixed morning, which makes the "no booking in
  the past" and "check in only on the day" rules deterministic.
"""
import os

# Settings are read when app.db is imported, so set them first.
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["GIT_SHA"] = "test-sha"

from datetime import date, datetime, time  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.db import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.services.clock import clinic_now  # noqa: E402

TODAY = date(2030, 1, 15)
NOW = datetime.combine(TODAY, time(9, 20))  # 09:20, so 09:00 and 09:15 are already past
TOMORROW = date(2030, 1, 16)


@pytest.fixture()
def session_factory():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture()
def client(session_factory):
    def test_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = test_db
    app.dependency_overrides[clinic_now] = lambda: NOW
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def make_doctor(client):
    def _make(**overrides):
        body = {"full_name": "Dr. Ananya Iyer", "specialty": "General Medicine", "room": "101"}
        body.update(overrides)
        response = client.post("/api/doctors", json=body)
        assert response.status_code == 201, response.text
        return response.json()

    return _make


@pytest.fixture()
def make_patient(client):
    counter = iter(range(100))

    def _make(**overrides):
        body = {
            "full_name": "Priya Sharma",
            "phone": f"98765{next(counter):05d}",
            "date_of_birth": "1991-04-12",
            "gender": "female",
        }
        body.update(overrides)
        response = client.post("/api/patients", json=body)
        assert response.status_code == 201, response.text
        return response.json()

    return _make


@pytest.fixture()
def book(client, make_doctor, make_patient):
    """Book an appointment; creates a doctor/patient when not given."""

    def _book(doctor=None, patient=None, on=TODAY, at="10:00", expect=201, **extra):
        doctor = doctor or make_doctor()
        patient = patient or make_patient()
        body = {
            "doctor_id": doctor["id"],
            "patient_id": patient["id"],
            "appointment_date": on.isoformat(),
            "slot_time": at,
            **extra,
        }
        response = client.post("/api/appointments", json=body)
        assert response.status_code == expect, response.text
        return response.json()

    return _book


@pytest.fixture()
def set_status(client):
    def _set(appointment_id, status, expect=200):
        response = client.patch(f"/api/appointments/{appointment_id}/status", json={"status": status})
        assert response.status_code == expect, response.text
        return response.json()

    return _set
