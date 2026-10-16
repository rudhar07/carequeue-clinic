# CareQueue: the application

CareQueue runs the front desk of a small outpatient clinic. Reception books patients into a
doctor's time slots, every booking gets a **token number**, and on the day the waiting room is
run from a **live queue**: check the patient in, call them in, complete the visit. The header
always shows today's numbers.

Repository: <https://github.com/rudhar07/carequeue-clinic>

| Layer | Tech |
|-------|------|
| Backend | Python 3.13, FastAPI, SQLAlchemy 2, Alembic, Pydantic v2, prometheus-fastapi-instrumentator |
| Database | PostgreSQL 17 (Compose/Kubernetes); in-memory SQLite in tests |
| Frontend | React 18 + Vite, plain CSS, Vitest + Testing Library |
| Runtime | Uvicorn (1 worker per container) behind nginx-unprivileged, which serves the SPA and proxies `/api` |

## Data model

```
doctors 1 ──< appointments >── 1 patients
```

| Table | Columns | Constraints / indexes |
|-------|---------|-----------------------|
| `doctors` | id, full_name, specialty, room, slot_minutes (15), start_time (09:00), end_time (17:00), is_active | `start_time < end_time`, `slot_minutes BETWEEN 5 AND 120`, index on specialty |
| `patients` | id, full_name, phone, date_of_birth, gender, created_at | `phone` UNIQUE (stored as 10 digits), `gender IN (female, male, other)`, index on full_name |
| `appointments` | id, patient_id → patients (CASCADE), doctor_id → doctors (RESTRICT), appointment_date, slot_time, reason, token_number, status, created_at, updated_at | `status` CHECK; **partial unique index** `uq_appointments_active_slot (doctor_id, appointment_date, slot_time) WHERE status <> 'cancelled'`; unique `(doctor_id, appointment_date, token_number)`; index `(appointment_date, status)`; index on patient_id |

All of it is created by one migration, `backend/alembic/versions/0001_create_clinic_tables.py`.

## API

All application routes are under `/api`. Errors use FastAPI's `{"detail": ...}` shape.

| Method | Path | What it does |
|--------|------|--------------|
| GET | `/api/doctors?active_only=&specialty=` | List doctors |
| POST | `/api/doctors` | Add a doctor (201) |
| GET / PUT | `/api/doctors/{id}` | Read / update (hours, room, active flag) |
| DELETE | `/api/doctors/{id}` | Delete; **deactivates** instead if the doctor has appointments |
| GET | `/api/doctors/{id}/slots?date=YYYY-MM-DD` | The day's slot grid: `free`, `booked` (with token) or `past` |
| GET | `/api/patients?q=&limit=&offset=` | List / search by name or phone fragment |
| POST | `/api/patients` | Register a patient (201; 409 duplicate phone; 422 invalid phone) |
| GET / PUT / DELETE | `/api/patients/{id}` | Read / update / delete (409 while an appointment is active) |
| GET | `/api/appointments?date=&doctor_id=&patient_id=&status=` | List with filters |
| POST | `/api/appointments` | Book: validates the slot, assigns the token (201) |
| GET / PUT / DELETE | `/api/appointments/{id}` | Read / reschedule a booked appointment / delete |
| PATCH | `/api/appointments/{id}/status` | `{"status": ...}`, validated against the state machine |
| GET | `/api/queue?doctor_id=&date=` | Live queue (default today): `now_serving`, `next_up`, `waiting_count`, `waiting`, `not_arrived`, `done` |
| GET | `/api/stats/today` | Today's count per status, active doctors, patients |
| GET | `/api/info` | `{app, version, commit}` (commit = `GIT_SHA`) |
| GET | `/health` | Liveness, never touches the DB |
| GET | `/ready` | Readiness: `SELECT 1`, 503 when the DB is down |
| GET | `/metrics` | Prometheus metrics |

Interactive docs: `/docs` on the backend (not proxied by nginx).

## Business rules

1. **Slot grid.** A doctor's slots start at `start_time` and step by `slot_minutes`; a slot must
   end by `end_time`. Booking a time that isn't on the grid (e.g. 10:07, or 17:00 for a 09:00-17:00
   doctor) returns **422**.
2. **No booking in the past.** Date + slot must be later than "now" in the clinic timezone
   (`CLINIC_TIMEZONE`, default Asia/Kolkata): **422**.
3. **No double booking.** A doctor/date/slot can hold only one appointment that isn't cancelled:
   **409**. The code checks first; the partial unique index is the backstop for races (an
   `IntegrityError` on commit also becomes 409). A cancelled slot can be booked again.
4. **Inactive doctors** can't be booked: **409**.
5. **Tokens** are sequential per doctor per day (`max + 1`) and never reused, even after a
   cancellation. Rescheduling to another doctor or day issues a new token.
6. **Status machine** (anything else is **409**):

   ```
   booked ──> checked_in ──> in_consultation ──> completed
     │            │
     ├──> cancelled <──┤
     └──> no_show  <───┘
   ```

   Check-in and call-in only work on the appointment day. A doctor sees one patient at a time:
   calling in a second patient while one is `in_consultation` is a 409.
7. **Queue order** is by token number, not arrival time.
8. **Edits and deletes.** Only `booked` appointments can be rescheduled. Visits that took place
   (`in_consultation`, `completed`) can't be deleted. A patient with an active appointment can't be
   deleted; otherwise the patient and their past visits are removed. A doctor with history is
   deactivated, not deleted.
9. **Patients.** Phone numbers are normalised (`+91 98765-43210` → `9876543210`), must be a valid
   Indian mobile number (10 digits starting with 6-9) and are unique. Date of birth can't be in the future.

## Observability

- HTTP metrics from the instrumentator: `http_requests_total{handler,method,status}`,
  `http_request_duration_seconds` (histogram), and more.
- Business metrics: `carequeue_appointments_booked_total`,
  `carequeue_appointments_status_total{status}`, `carequeue_queue_waiting{doctor}` (gauge, updated
  on status changes, queue views and every `/api/stats/today` poll).
- Logs are JSON, one line per event, including one access line per request
  (`method`, `path`, `status`, `duration_ms`). Probes and scrapes aren't logged.

## Configuration (env)

| Variable | Default | Notes |
|----------|---------|-------|
| `DATABASE_URL` | `sqlite:///./carequeue-dev.db` | Compose/Helm set `postgresql+psycopg://...` |
| `CORS_ORIGINS` | `http://localhost:3000,http://localhost:5173` | Comma separated |
| `LOG_LEVEL` | `INFO` | |
| `CLINIC_TIMEZONE` | `Asia/Kolkata` | Decides "today" and "past" |
| `GIT_SHA`, `APP_VERSION` | `local`, `1.0.0` | Shown by `/api/info`; also image build args |
| `RUN_MIGRATIONS` | `false` | Entrypoint runs `alembic upgrade head` first |
| `RUN_SEED`, `SEED_DEMO_QUEUE` | `false` | Entrypoint runs `python -m app.seed [--demo-queue]` |
| `BACKEND_URL` (frontend) | `http://backend:8000` | nginx `/api` upstream, rendered from `nginx.conf.template` |

## Running it

```bash
docker compose up --build            # http://localhost:3000 (FRONTEND_PORT to change it)
```

Compose starts Postgres, runs the migration and the idempotent seed (4 doctors, 12 patients,
and a demo queue for today), then starts the UI. All demo names and numbers are made up.

Without Docker:

```bash
cd backend && pip install -r requirements-dev.txt
pytest                                # 51 tests, coverage gate 80%
alembic upgrade head && python -m app.seed --demo-queue && uvicorn app.main:app --reload
cd ../frontend && npm ci && npm test -- --run && npm run dev   # http://localhost:5173
```

Helpers in `scripts/`: `api-flow.sh` (end-to-end API walkthrough with curl), `load-test.sh`
(traffic for the Grafana panels) and `screenshots.py` (Playwright screenshots of the UI).
