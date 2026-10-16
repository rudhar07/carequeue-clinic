"""/api/patients CRUD, phone validation/uniqueness and search."""
import pytest


def test_create_patient_normalises_phone(client, make_patient):
    patient = make_patient(phone="+91 98765-43210", full_name="  Rahul   Verma ")
    assert patient["phone"] == "9876543210"
    assert patient["full_name"] == "Rahul Verma"
    assert client.get(f"/api/patients/{patient['id']}").json()["phone"] == "9876543210"


@pytest.mark.parametrize("phone", ["12345", "5876543210", "98765432101", "98765abcde"])
def test_invalid_phone_is_rejected(client, phone):
    body = {"full_name": "Sneha Patil", "phone": phone, "date_of_birth": "2016-07-21", "gender": "female"}
    response = client.post("/api/patients", json=body)
    assert response.status_code == 422
    assert "phone" in response.text


def test_duplicate_phone_is_409(client, make_patient):
    make_patient(phone="9876500001")
    body = {"full_name": "Someone Else", "phone": "09876500001", "date_of_birth": "1990-01-01", "gender": "male"}
    response = client.post("/api/patients", json=body)
    assert response.status_code == 409
    assert "phone" in response.json()["detail"]


def test_future_date_of_birth_is_rejected(client):
    body = {"full_name": "Baby Kumar", "phone": "9123456789", "date_of_birth": "2999-01-01", "gender": "other"}
    assert client.post("/api/patients", json=body).status_code == 422


def test_invalid_gender_is_rejected(client):
    body = {"full_name": "Test Person", "phone": "9123456789", "date_of_birth": "1990-01-01", "gender": "x"}
    assert client.post("/api/patients", json=body).status_code == 422


def test_search_by_name_or_phone(client, make_patient):
    make_patient(full_name="Vikram Nair", phone="9000011111")
    make_patient(full_name="Aisha Khan", phone="8000022222")
    assert [p["full_name"] for p in client.get("/api/patients", params={"q": "vik"}).json()] == ["Vikram Nair"]
    assert [p["full_name"] for p in client.get("/api/patients", params={"q": "80000"}).json()] == ["Aisha Khan"]
    assert len(client.get("/api/patients").json()) == 2


def test_update_patient_and_phone_conflict(client, make_patient):
    first = make_patient(phone="9000011111")
    second = make_patient(phone="9000022222")
    body = {**second, "full_name": "Divya Menon", "phone": "9000022222"}
    response = client.put(f"/api/patients/{second['id']}", json=body)
    assert response.status_code == 200
    assert response.json()["full_name"] == "Divya Menon"

    clash = {**body, "phone": first["phone"]}
    assert client.put(f"/api/patients/{second['id']}", json=clash).status_code == 409


def test_delete_patient(client, make_patient):
    patient = make_patient()
    assert client.delete(f"/api/patients/{patient['id']}").status_code == 204
    assert client.get(f"/api/patients/{patient['id']}").status_code == 404
    assert client.delete(f"/api/patients/{patient['id']}").status_code == 404


def test_patient_with_active_appointment_cannot_be_deleted(client, book, set_status):
    appt = book()
    assert client.delete(f"/api/patients/{appt['patient_id']}").status_code == 409
    set_status(appt["id"], "cancelled")
    assert client.delete(f"/api/patients/{appt['patient_id']}").status_code == 204
    assert client.get(f"/api/appointments/{appt['id']}").status_code == 404
