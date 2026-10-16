"""/api/doctors CRUD, deactivation and the slot grid."""
from conftest import TODAY, TOMORROW


def test_create_and_get_doctor_with_default_hours(client, make_doctor):
    doctor = make_doctor()
    assert doctor["slot_minutes"] == 15
    assert doctor["start_time"] == "09:00:00"
    assert doctor["end_time"] == "17:00:00"
    assert doctor["is_active"] is True
    assert client.get(f"/api/doctors/{doctor['id']}").json() == doctor


def test_list_doctors_filters(client, make_doctor):
    make_doctor(full_name="Dr. Rohan Mehta", specialty="Pediatrics")
    inactive = make_doctor(full_name="Dr. Kavya Reddy", specialty="Dermatology")
    client.put(f"/api/doctors/{inactive['id']}", json={**inactive, "is_active": False})

    assert len(client.get("/api/doctors").json()) == 2
    active = client.get("/api/doctors", params={"active_only": True}).json()
    assert [d["full_name"] for d in active] == ["Dr. Rohan Mehta"]
    peds = client.get("/api/doctors", params={"specialty": "Pediatrics"}).json()
    assert len(peds) == 1


def test_update_doctor_hours(client, make_doctor):
    doctor = make_doctor()
    body = {**doctor, "room": "B-12", "slot_minutes": 30, "start_time": "10:00", "end_time": "13:00"}
    response = client.put(f"/api/doctors/{doctor['id']}", json=body)
    assert response.status_code == 200
    assert response.json()["room"] == "B-12"
    assert response.json()["slot_minutes"] == 30


def test_doctor_hours_must_be_ordered(client):
    body = {"full_name": "Dr. Test Case", "specialty": "ENT", "room": "1", "start_time": "17:00", "end_time": "09:00"}
    assert client.post("/api/doctors", json=body).status_code == 422


def test_unknown_doctor_is_404(client):
    assert client.get("/api/doctors/999").status_code == 404
    assert client.get("/api/doctors/999/slots", params={"date": TODAY.isoformat()}).status_code == 404


def test_delete_doctor_without_history_removes_it(client, make_doctor):
    doctor = make_doctor()
    response = client.delete(f"/api/doctors/{doctor['id']}")
    assert response.json() == {"id": doctor["id"], "action": "deleted"}
    assert client.get(f"/api/doctors/{doctor['id']}").status_code == 404


def test_delete_doctor_with_appointments_only_deactivates(client, book):
    appt = book()
    response = client.delete(f"/api/doctors/{appt['doctor_id']}")
    assert response.json()["action"] == "deactivated"
    assert client.get(f"/api/doctors/{appt['doctor_id']}").json()["is_active"] is False


def test_slot_grid_marks_free_booked_and_past(client, book, make_doctor):
    doctor = make_doctor(start_time="09:00", end_time="10:00", slot_minutes=15)
    book(doctor=doctor, at="09:30")
    grid = client.get(f"/api/doctors/{doctor['id']}/slots", params={"date": TODAY.isoformat()}).json()
    statuses = {s["time"]: s["status"] for s in grid["slots"]}
    # clock is pinned at 09:20 on TODAY
    assert statuses == {"09:00:00": "past", "09:15:00": "past", "09:30:00": "booked", "09:45:00": "free"}
    assert grid["free_count"] == 1
    assert grid["slots"][2]["token_number"] == 1

    tomorrow = client.get(f"/api/doctors/{doctor['id']}/slots", params={"date": TOMORROW.isoformat()}).json()
    assert tomorrow["free_count"] == 4
