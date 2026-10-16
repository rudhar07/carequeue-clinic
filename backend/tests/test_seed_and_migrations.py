"""The seed is idempotent and the Alembic migration builds the same schema."""
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, select

from app.models import Appointment, Doctor, Patient
from app.seed import DOCTORS, PATIENTS, seed_demo_queue, seed_reference_data
from conftest import TODAY

BACKEND = Path(__file__).resolve().parents[1]


def test_seed_is_idempotent(session_factory):
    with session_factory() as db:
        assert seed_reference_data(db) == (len(DOCTORS), len(PATIENTS))
        assert seed_reference_data(db) == (0, 0)
        first = seed_demo_queue(db, TODAY)
        assert first > 0
        assert seed_demo_queue(db, TODAY) == 0
        assert len(db.scalars(select(Doctor)).all()) == len(DOCTORS)
        assert len(db.scalars(select(Patient)).all()) == len(PATIENTS)
        statuses = {a.status for a in db.scalars(select(Appointment)).all()}
        assert {"completed", "in_consultation", "checked_in", "booked"} <= statuses


def test_alembic_upgrade_and_downgrade(tmp_path):
    url = f"sqlite:///{tmp_path / 'migrate.db'}"
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")

    engine = create_engine(url)
    try:
        inspector = inspect(engine)
        assert {"doctors", "patients", "appointments", "alembic_version"} <= set(inspector.get_table_names())
        indexes = {ix["name"]: ix for ix in inspector.get_indexes("appointments")}
        assert indexes["uq_appointments_active_slot"]["unique"]

        command.downgrade(cfg, "base")
        assert "appointments" not in inspect(engine).get_table_names()
    finally:
        engine.dispose()
