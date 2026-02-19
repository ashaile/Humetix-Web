"""add operation calendar days table

Revision ID: 9c8d1b2e4f77
Revises: f2c8d10a9b3e
Create Date: 2026-02-19 22:20:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "9c8d1b2e4f77"
down_revision = "f2c8d10a9b3e"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "operation_calendar_days",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column("day_type", sa.String(length=20), nullable=False),
        sa.Column("note", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("work_date", name="uq_operation_calendar_work_date"),
    )
    op.create_index(
        "ix_operation_calendar_work_date",
        "operation_calendar_days",
        ["work_date"],
        unique=False,
    )


def downgrade():
    op.drop_index("ix_operation_calendar_work_date", table_name="operation_calendar_days")
    op.drop_table("operation_calendar_days")
