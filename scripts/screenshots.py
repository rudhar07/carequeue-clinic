"""Take the README screenshots of a running CareQueue with headless Chromium.

    pip install playwright && python -m playwright install chromium
    BASE_URL=http://localhost:3000 OUT_DIR=docs/screenshots python scripts/screenshots.py

Needs the demo seed (`python -m app.seed --demo-queue`, on by default in compose).
It books a few appointments for tomorrow through the API so the slot grid shows
booked slots, then books one more through the UI itself.
"""
import json
import os
import urllib.request
from datetime import date, timedelta
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

BASE_URL = os.environ.get("BASE_URL", "http://localhost:3000").rstrip("/")
OUT = Path(os.environ.get("OUT_DIR", "docs/screenshots"))


def api(method: str, path: str, body: dict | None = None):
    req = urllib.request.Request(
        f"{BASE_URL}/api{path}",
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as err:
        if err.code == 409:  # already booked by an earlier run
            return None
        raise


def prepare_tomorrow(doctor_id: int, tomorrow: str) -> None:
    patients = api("GET", "/patients")
    for patient, slot in zip(patients[:4], ["11:00", "11:15", "11:45", "12:30"]):
        api("POST", "/appointments", {
            "patient_id": patient["id"], "doctor_id": doctor_id,
            "appointment_date": tomorrow, "slot_time": slot, "reason": "Follow-up visit",
        })


def shot(page: Page, name: str, full_page: bool = True) -> None:
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(300)  # let fonts/layout settle
    page.screenshot(path=str(OUT / name), full_page=full_page)
    print("saved", OUT / name)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    tomorrow = (date.fromisoformat(api("GET", "/stats/today")["date"]) + timedelta(days=1)).isoformat()
    doctor = next(d for d in api("GET", "/doctors") if d["specialty"] == "General Medicine")
    prepare_tomorrow(doctor["id"], tomorrow)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1366, "height": 900}, device_scale_factor=1)

        # 1. Booking: doctor + tomorrow -> slot grid, pick patient, book, token shown.
        page.goto(f"{BASE_URL}/#book")
        page.get_by_label("Doctor").select_option(str(doctor["id"]))
        page.get_by_label("Date").fill(tomorrow)
        page.get_by_role("option", name="10:30 AM").click()
        page.get_by_label("Search by mobile number or name").fill("Meera")
        page.get_by_role("button", name="Meera Joshi").click()
        page.get_by_label("Reason for visit").fill("Mild fever and cough for 2 days")
        page.get_by_role("button", name="Book appointment").click()
        page.get_by_text("booked for Meera Joshi").wait_for()
        shot(page, "01-book-appointment-slot-grid.png")
        page.locator(".toast").wait_for(state="detached")  # keep the toast out of the next shots

        # 2. Live queue for the General Medicine doctor (seeded demo queue).
        page.goto(f"{BASE_URL}/#queue")
        page.get_by_role("tab", name=doctor["full_name"]).click()
        page.get_by_text("Now serving").wait_for()
        shot(page, "02-live-queue-now-serving.png")

        # 3. Patients list.
        page.goto(f"{BASE_URL}/#patients")
        page.get_by_text("Priya Sharma").wait_for()
        shot(page, "03-patients.png")

        # 4. Doctors.
        page.goto(f"{BASE_URL}/#doctors")
        page.get_by_text("Dr. Arjun Singh").wait_for()
        shot(page, "04-doctors.png")

        # 5-6. Phone width (390 px): live queue and booking.
        mobile = browser.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=2,
                                  is_mobile=True, has_touch=True)
        mobile.goto(f"{BASE_URL}/#queue")
        mobile.get_by_text("Now serving").wait_for()
        shot(mobile, "05-mobile-390-live-queue.png")
        mobile.goto(f"{BASE_URL}/#book")
        mobile.get_by_label("Date").fill(tomorrow)
        mobile.get_by_role("option", name="11:00 AM").wait_for()
        shot(mobile, "06-mobile-390-booking.png")

        browser.close()


if __name__ == "__main__":
    main()
