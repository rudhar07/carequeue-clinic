"""/api/queue (live queue) and /api/stats/today."""
from conftest import TODAY, TOMORROW


def test_queue_orders_by_token_and_shows_now_serving(client, book, make_doctor, set_status):
    doctor = make_doctor()
    appts = [book(doctor=doctor, at=t) for t in ("10:00", "10:15", "10:30", "10:45", "11:00")]
    t1, t2, t3, t4, t5 = (a["id"] for a in appts)
    set_status(t1, "checked_in")
    set_status(t1, "in_consultation")
    set_status(t1, "completed")
    # Token 4 arrives before token 3; the queue still runs by token number.
    set_status(t4, "checked_in")
    set_status(t3, "checked_in")
    set_status(t2, "checked_in")
    set_status(t2, "in_consultation")

    queue = client.get("/api/queue", params={"doctor_id": doctor["id"]}).json()
    assert queue["date"] == TODAY.isoformat()
    assert queue["now_serving"]["token_number"] == 2
    assert queue["next_up"]["token_number"] == 3
    assert queue["waiting_count"] == 2
    assert [a["token_number"] for a in queue["waiting"]] == [3, 4]
    assert [a["token_number"] for a in queue["not_arrived"]] == [5]
    assert [a["token_number"] for a in queue["done"]] == [1]
    assert t5 == queue["not_arrived"][0]["id"]


def test_empty_queue_and_other_days(client, book, make_doctor):
    doctor = make_doctor()
    book(doctor=doctor, on=TOMORROW)
    today = client.get("/api/queue", params={"doctor_id": doctor["id"]}).json()
    assert today["now_serving"] is None and today["next_up"] is None and today["waiting_count"] == 0
    tomorrow = client.get("/api/queue", params={"doctor_id": doctor["id"], "date": TOMORROW.isoformat()}).json()
    assert len(tomorrow["not_arrived"]) == 1


def test_queue_requires_existing_doctor(client):
    assert client.get("/api/queue").status_code == 422
    assert client.get("/api/queue", params={"doctor_id": 7}).status_code == 404


def test_today_stats_count_per_status(client, book, make_doctor, set_status):
    doctor = make_doctor()
    a = book(doctor=doctor, at="10:00")
    b = book(doctor=doctor, at="10:15")
    book(doctor=doctor, at="10:30")
    book(doctor=doctor, on=TOMORROW)  # not today: not counted
    set_status(a["id"], "checked_in")
    set_status(b["id"], "cancelled")

    stats = client.get("/api/stats/today").json()
    assert stats["date"] == TODAY.isoformat()
    assert stats["total"] == 3
    assert stats["by_status"] == {
        "booked": 1, "checked_in": 1, "in_consultation": 0, "completed": 0, "cancelled": 1, "no_show": 0,
    }
    assert stats["active_doctors"] == 1
    assert stats["patients"] == 4
    metrics = client.get("/metrics").text
    assert 'carequeue_queue_waiting{doctor="Dr. Ananya Iyer"} 1.0' in metrics
