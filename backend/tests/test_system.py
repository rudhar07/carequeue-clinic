"""Probes, build info, the Prometheus endpoint and structured logging."""
import json
import logging
import sys

from sqlalchemy.exc import OperationalError

from app.db import get_db
from app.logging_config import JsonFormatter
from app.main import app


def test_health_is_ok_without_database(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_reports_database_up(client):
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json()["database"] == "up"


def test_ready_returns_503_when_database_is_down(client):
    class BrokenSession:
        def execute(self, *_args, **_kwargs):
            raise OperationalError("SELECT 1", {}, Exception("connection refused"))

    app.dependency_overrides[get_db] = lambda: BrokenSession()
    response = client.get("/ready")
    assert response.status_code == 503
    assert response.json()["status"] == "unavailable"


def test_info_reports_app_and_commit(client):
    body = client.get("/api/info").json()
    assert body["app"] == "carequeue"
    assert body["commit"] == "test-sha"
    assert body["version"]


def test_metrics_expose_http_and_business_metrics(client, book, set_status):
    appt = book()
    set_status(appt["id"], "checked_in")
    client.get("/api/queue", params={"doctor_id": appt["doctor_id"]})

    response = client.get("/metrics")
    assert response.status_code == 200
    text = response.text
    assert "http_requests_total" in text
    assert "http_request_duration_seconds_bucket" in text
    assert "carequeue_appointments_booked_total" in text
    assert 'carequeue_appointments_status_total{status="checked_in"}' in text
    assert 'carequeue_queue_waiting{doctor="Dr. Ananya Iyer"} 1.0' in text


def test_queue_gauge_drops_series_for_removed_doctor(client, book, set_status):
    appt = book()
    set_status(appt["id"], "checked_in")
    client.get("/api/stats/today")
    assert 'carequeue_queue_waiting{doctor="Dr. Ananya Iyer"}' in client.get("/metrics").text

    assert client.delete(f"/api/doctors/{appt['doctor_id']}").status_code in (200, 204)
    client.get("/api/stats/today")
    assert 'carequeue_queue_waiting{doctor="Dr. Ananya Iyer"}' not in client.get("/metrics").text


def test_cors_allows_configured_origin(client):
    response = client.options(
        "/api/doctors",
        headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"},
    )
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_json_log_formatter_includes_extra_fields_and_errors():
    try:
        raise ValueError("boom")
    except ValueError:
        record = logging.makeLogRecord(
            {"name": "carequeue.test", "levelname": "ERROR", "msg": "booking failed",
             "doctor_id": 3, "exc_info": sys.exc_info()}
        )
    line = json.loads(JsonFormatter().format(record))
    assert line["msg"] == "booking failed"
    assert line["doctor_id"] == 3
    assert "ValueError: boom" in line["exc"]
