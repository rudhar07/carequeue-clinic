"""Create doctors, patients and appointments (with the double-booking guard).

Revision ID: 0001
Revises:
Create Date: 2026-10-16
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

STATUSES = ("booked", "checked_in", "in_consultation", "completed", "cancelled", "no_show")
GENDERS = ("female", "male", "other")


def upgrade() -> None:
    op.create_table(
        "doctors",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("full_name", sa.String(120), nullable=False),
        sa.Column("specialty", sa.String(80), nullable=False),
        sa.Column("room", sa.String(20), nullable=False),
        sa.Column("slot_minutes", sa.Integer(), nullable=False, server_default="15"),
        sa.Column("start_time", sa.Time(), nullable=False, server_default="09:00:00"),
        sa.Column("end_time", sa.Time(), nullable=False, server_default="17:00:00"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.CheckConstraint("start_time < end_time", name="ck_doctors_hours"),
        sa.CheckConstraint("slot_minutes BETWEEN 5 AND 120", name="ck_doctors_slot_minutes"),
    )
    op.create_index("ix_doctors_specialty", "doctors", ["specialty"])

    op.create_table(
        "patients",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("full_name", sa.String(120), nullable=False),
        sa.Column("phone", sa.String(10), nullable=False, unique=True),
        sa.Column("date_of_birth", sa.Date(), nullable=False),
        sa.Column("gender", sa.String(10), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(f"gender IN {GENDERS}", name="ck_patients_gender"),
    )
    op.create_index("ix_patients_full_name", "patients", ["full_name"])

    op.create_table(
        "appointments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("doctor_id", sa.Integer(), sa.ForeignKey("doctors.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("appointment_date", sa.Date(), nullable=False),
        sa.Column("slot_time", sa.Time(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("token_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="booked"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(f"status IN {STATUSES}", name="ck_appointments_status"),
    )
    op.create_index("ix_appointments_patient_id", "appointments", ["patient_id"])
    op.create_index("ix_appointments_date_status", "appointments", ["appointment_date", "status"])
    op.create_index(
        "uq_appointments_token", "appointments", ["doctor_id", "appointment_date", "token_number"], unique=True
    )
    # No double booking: a slot can hold only one appointment that is not cancelled.
    op.create_index(
        "uq_appointments_active_slot",
        "appointments",
        ["doctor_id", "appointment_date", "slot_time"],
        unique=True,
        postgresql_where=sa.text("status <> 'cancelled'"),
        sqlite_where=sa.text("status <> 'cancelled'"),
    )


def downgrade() -> None:
    op.drop_table("appointments")
    op.drop_table("patients")
    op.drop_table("doctors")
