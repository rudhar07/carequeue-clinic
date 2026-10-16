"""/api/appointments: booking rules, rescheduling and status transitions."""
from datetime import time, timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Appointment
from conftest import TODAY, TOMORROW


def test_booking_assigns_sequential_tokens_per_doctor_per_day(book, make_doctor):
    doctor = make_doctor()
    other = make_doctor(full_name="Dr. Rohan Mehta", specialty="Pediatrics")
    first = book(doctor=doctor, at="10:00", reason="  Fever  ")
    second = book(doctor=doctor, at="10:15")
    other_first = book(doctor=other, at="10:00")
    tomorrow_first = book(doctor=doctor, on=TOMORROW, at="10:00")

    assert (first["token_number"], second["token_number"]) == (1, 2)
    assert other_first["token_number"] == 1
    assert tomorrow_first["token_number"] == 1
    assert first["status"] == "booked"
    assert first["reason"] == "Fever"
    assert first["patient"]["full_name"] == "Priya Sharma"
    assert first["doctor"]["specialty"] == "General Medicine"


def test_double_booking_same_slot_is_409(book, make_doctor):
    doctor = make_doctor()
    book(doctor=doctor, at="11:00")
    response = book(doctor=doctor, at="11:00", expect=409)
    assert response["detail"] == "This slot is already booked"


def test_cancelled_slot_can_be_booked_again_with_a_new_token(book, make_doctor, set_status):
    doctor = make_doctor()
    first = book(doctor=doctor, at="11:00")
    set_status(first["id"], "cancelled")
    again = book(doctor=doctor, at="11:00")
    assert again["token_number"] == 2  # tokens are never reused


def test_database_index_blocks_double_booking(session_factory, client, book):
    """The partial unique index is the backstop even if the code check is bypassed."""
    appt = book(at="12:00")
    with session_factory() as db:
        db.add(Appointment(patient_id=appt["patient_id"], doctor_id=appt["doctor_id"],
                           appointment_date=TODAY, slot_time=time(12, 0),
                           token_number=99, status="booked"))
        with pytest.raises(IntegrityError):
            db.commit()


def test_slot_outside_hours_or_off_grid_is_422(book, make_doctor):
    doctor = make_doctor()  # 09:00-17:00, every 15 minutes
    assert "not a valid slot" in book(doctor=doctor, at="18:00", expect=422)["detail"]
    book(doctor=doctor, at="16:45")  # last slot of the day is fine
    assert "not a valid slot" in book(doctor=doctor, at="17:00", expect=422)["detail"]
    assert "not a valid slot" in book(doctor=doctor, at="10:07", expect=422)["detail"]


def test_past_slot_and_past_date_are_rejected(book, make_doctor):
    doctor = make_doctor()
    assert book(doctor=doctor, at="09:15", expect=422)["detail"] == "Cannot book a slot in the past"
    yesterday = TODAY - timedelta(days=1)
    assert book(doctor=doctor, on=yesterday, at="12:00", expect=422)["detail"] == "Cannot book a slot in the past"


def test_inactive_doctor_cannot_be_booked(client, book, make_doctor):
    doctor = make_doctor()
    client.put(f"/api/doctors/{doctor['id']}", json={**doctor, "is_active": False})
    assert "not taking appointments" in book(doctor=doctor, expect=409)["detail"]


def test_unknown_patient_or_doctor_is_404(client, make_doctor):
    doctor = make_doctor()
    body = {"doctor_id": doctor["id"], "patient_id": 42, "appointment_date": TODAY.isoformat(), "slot_time": "10:00"}
    assert client.post("/api/appointments", json=body).status_code == 404
    assert client.get("/api/appointments/42").status_code == 404


def test_list_appointments_with_filters(client, book, make_doctor, make_patient, set_status):
    doctor = make_doctor()
    patient = make_patient()
    a = book(doctor=doctor, patient=patient, at="10:00")
    book(doctor=doctor, at="10:30")
    book(doctor=doctor, patient=patient, on=TOMORROW, at="10:00")
    set_status(a["id"], "checked_in")

    assert len(client.get("/api/appointments").json()) == 3
    assert len(client.get("/api/appointments", params={"date": TODAY.isoformat()}).json()) == 2
    assert len(client.get("/api/appointments", params={"patient_id": patient["id"]}).json()) == 2
    assert len(client.get("/api/appointments", params={"doctor_id": doctor["id"]}).json()) == 3
    checked = client.get("/api/appointments", params={"status": "checked_in"}).json()
    assert [x["id"] for x in checked] == [a["id"]]


def test_full_visit_workflow(book, set_status):
    appt = book()
    for status in ("checked_in", "in_consultation", "completed"):
        assert set_status(appt["id"], status)["status"] == status


def test_invalid_status_transitions_are_409(book, set_status):
    appt = book()
    assert "Cannot change status from booked to completed" in set_status(appt["id"], "completed", 409)["detail"]
    set_status(appt["id"], "cancelled")
    set_status(appt["id"], "checked_in", 409)  # cancelled is final


def test_no_show_allowed_from_booked_and_checked_in(book, make_doctor, set_status):
    doctor = make_doctor()
    a = book(doctor=doctor, at="10:00")
    b = book(doctor=doctor, at="10:15")
    set_status(a["id"], "no_show")
    set_status(b["id"], "checked_in")
    set_status(b["id"], "no_show")
    set_status(b["id"], "booked", 409)


def test_check_in_only_on_appointment_day(book, set_status):
    appt = book(on=TOMORROW)
    assert "appointment day" in set_status(appt["id"], "checked_in", 409)["detail"]


def test_doctor_sees_one_patient_at_a_time(book, make_doctor, set_status):
    doctor = make_doctor()
    a = book(doctor=doctor, at="10:00")
    b = book(doctor=doctor, at="10:15")
    for appt in (a, b):
        set_status(appt["id"], "checked_in")
    set_status(a["id"], "in_consultation")
    assert "still with token #1" in set_status(b["id"], "in_consultation", 409)["detail"]
    set_status(a["id"], "completed")
    set_status(b["id"], "in_consultation")


def test_unknown_status_value_is_422(client, book):
    appt = book()
    response = client.patch(f"/api/appointments/{appt['id']}/status", json={"status": "teleported"})
    assert response.status_code == 422


def test_reschedule_booked_appointment(client, book, make_doctor):
    doctor = make_doctor()
    other = make_doctor(full_name="Dr. Arjun Singh", specialty="Orthopedics", slot_minutes=30)
    appt = book(doctor=doctor, at="10:00")
    book(doctor=doctor, at="10:15")

    def put(**changes):
        body = {"doctor_id": doctor["id"], "appointment_date": TODAY.isoformat(), "slot_time": "10:00",
                "reason": "Follow-up", **changes}
        return client.put(f"/api/appointments/{appt['id']}", json=body)

    assert put().json()["reason"] == "Follow-up"  # same slot, just a new reason
    assert put(slot_time="10:15").status_code == 409  # taken
    moved = put(slot_time="11:00").json()
    assert (moved["slot_time"], moved["token_number"]) == ("11:00:00", 1)  # same day keeps the token
    other_doc = put(doctor_id=other["id"], slot_time="13:30").json()
    assert other_doc["doctor"]["full_name"] == "Dr. Arjun Singh"
    assert other_doc["token_number"] == 1


def test_only_booked_appointments_can_be_rescheduled(client, book, set_status):
    appt = book()
    set_status(appt["id"], "checked_in")
    body = {"doctor_id": appt["doctor_id"], "appointment_date": TODAY.isoformat(), "slot_time": "12:00"}
    assert client.put(f"/api/appointments/{appt['id']}", json=body).status_code == 409


def test_delete_appointment_rules(client, book, make_doctor, set_status):
    doctor = make_doctor()
    booked = book(doctor=doctor, at="10:00")
    visited = book(doctor=doctor, at="10:15")
    set_status(visited["id"], "checked_in")
    set_status(visited["id"], "in_consultation")

    assert client.delete(f"/api/appointments/{booked['id']}").status_code == 204
    assert client.get(f"/api/appointments/{booked['id']}").status_code == 404
    assert client.delete(f"/api/appointments/{visited['id']}").status_code == 409
