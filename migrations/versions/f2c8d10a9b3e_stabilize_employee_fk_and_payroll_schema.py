"""stabilize employee foreign keys and payroll schema

Revision ID: f2c8d10a9b3e
Revises: 5b29f1bd1c5e
Create Date: 2026-02-19 22:10:00

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f2c8d10a9b3e"
down_revision = "5b29f1bd1c5e"
branch_labels = None
depends_on = None


def _normalize_birth(value: str) -> str:
    raw = "".join(ch for ch in (value or "") if ch.isdigit())
    if len(raw) >= 6:
        return raw[:6]
    return "000000"


def _normalize_name(value: str, fallback: str) -> str:
    name = (value or "").strip()
    if not name:
        name = fallback
    return name[:50]


def _ensure_employee(conn, name: str, birth_date: str) -> int:
    row = conn.execute(
        sa.text(
            "SELECT id FROM employees WHERE name = :name AND birth_date = :birth_date LIMIT 1"
        ),
        {"name": name, "birth_date": birth_date},
    ).fetchone()
    if row:
        return int(row[0])

    conn.execute(
        sa.text(
            """
            INSERT INTO employees (name, birth_date, work_type, is_active, created_at, updated_at)
            VALUES (:name, :birth_date, 'weekly', 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """
        ),
        {"name": name, "birth_date": birth_date},
    )

    row = conn.execute(
        sa.text(
            "SELECT id FROM employees WHERE name = :name AND birth_date = :birth_date ORDER BY id DESC LIMIT 1"
        ),
        {"name": name, "birth_date": birth_date},
    ).fetchone()
    return int(row[0])


def _backfill_employee_ids(conn):
    conn.execute(
        sa.text(
            """
            UPDATE attendance_records
            SET employee_id = emp_id
            WHERE employee_id IS NULL
              AND emp_id IS NOT NULL
              AND EXISTS (SELECT 1 FROM employees e WHERE e.id = attendance_records.emp_id)
            """
        )
    )
    conn.execute(
        sa.text(
            """
            UPDATE advance_requests
            SET employee_id = emp_id
            WHERE employee_id IS NULL
              AND emp_id IS NOT NULL
              AND EXISTS (SELECT 1 FROM employees e WHERE e.id = advance_requests.emp_id)
            """
        )
    )
    conn.execute(
        sa.text(
            """
            UPDATE payslips
            SET employee_id = emp_id
            WHERE employee_id IS NULL
              AND emp_id IS NOT NULL
              AND EXISTS (SELECT 1 FROM employees e WHERE e.id = payslips.emp_id)
            """
        )
    )

    attendance_rows = conn.execute(
        sa.text(
            """
            SELECT id, emp_name, birth_date
            FROM attendance_records
            WHERE employee_id IS NULL
            """
        )
    ).fetchall()
    for row in attendance_rows:
        record_id = int(row[0])
        name = _normalize_name(row[1], f"LEGACY_ATT_{record_id}")
        birth = _normalize_birth(str(row[2] or ""))
        employee_id = _ensure_employee(conn, name, birth)
        conn.execute(
            sa.text(
                """
                UPDATE attendance_records
                SET employee_id = :employee_id,
                    emp_name = :name,
                    birth_date = :birth
                WHERE id = :record_id
                """
            ),
            {
                "employee_id": employee_id,
                "name": name,
                "birth": birth,
                "record_id": record_id,
            },
        )

    advance_rows = conn.execute(
        sa.text(
            """
            SELECT id, emp_name, birth_date
            FROM advance_requests
            WHERE employee_id IS NULL
            """
        )
    ).fetchall()
    for row in advance_rows:
        request_id = int(row[0])
        name = _normalize_name(row[1], f"LEGACY_ADV_{request_id}")
        birth = _normalize_birth(str(row[2] or ""))
        employee_id = _ensure_employee(conn, name, birth)
        conn.execute(
            sa.text(
                """
                UPDATE advance_requests
                SET employee_id = :employee_id,
                    emp_name = :name,
                    birth_date = :birth
                WHERE id = :request_id
                """
            ),
            {
                "employee_id": employee_id,
                "name": name,
                "birth": birth,
                "request_id": request_id,
            },
        )

    payslip_rows = conn.execute(
        sa.text(
            """
            SELECT id, emp_name
            FROM payslips
            WHERE employee_id IS NULL
            """
        )
    ).fetchall()
    for row in payslip_rows:
        payslip_id = int(row[0])
        name = _normalize_name(row[1], f"LEGACY_PAY_{payslip_id}")
        # payslip에는 생년월일이 없으므로 안전한 placeholder로 고정
        birth = "000000"
        employee_id = _ensure_employee(conn, name, birth)
        conn.execute(
            sa.text(
                """
                UPDATE payslips
                SET employee_id = :employee_id,
                    emp_name = :name
                WHERE id = :payslip_id
                """
            ),
            {
                "employee_id": employee_id,
                "name": name,
                "payslip_id": payslip_id,
            },
        )


def upgrade():
    with op.batch_alter_table("attendance_records", schema=None) as batch_op:
        batch_op.add_column(sa.Column("employee_id", sa.Integer(), nullable=True))

    with op.batch_alter_table("advance_requests", schema=None) as batch_op:
        batch_op.add_column(sa.Column("employee_id", sa.Integer(), nullable=True))

    with op.batch_alter_table("payslips", schema=None) as batch_op:
        batch_op.add_column(sa.Column("employee_id", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column("holiday_hours", sa.Float(), nullable=False, server_default="0")
        )
        batch_op.add_column(
            sa.Column("holiday_pay", sa.Integer(), nullable=False, server_default="0")
        )

    conn = op.get_bind()
    _backfill_employee_ids(conn)

    with op.batch_alter_table("attendance_records", schema=None) as batch_op:
        batch_op.alter_column("employee_id", existing_type=sa.Integer(), nullable=False)
        batch_op.alter_column(
            "birth_date", existing_type=sa.String(length=8), type_=sa.String(length=6), nullable=False
        )
        batch_op.create_foreign_key(
            "fk_attendance_employee_id",
            "employees",
            ["employee_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch_op.create_index("ix_attendance_employee_date", ["employee_id", "work_date"], unique=False)
        batch_op.create_unique_constraint(
            "uq_attendance_employee_date", ["employee_id", "work_date"]
        )

    with op.batch_alter_table("advance_requests", schema=None) as batch_op:
        batch_op.alter_column("employee_id", existing_type=sa.Integer(), nullable=False)
        batch_op.alter_column(
            "birth_date", existing_type=sa.String(length=6), nullable=False
        )
        batch_op.alter_column(
            "work_type", existing_type=sa.String(length=10), nullable=False
        )
        batch_op.alter_column(
            "status", existing_type=sa.String(length=20), nullable=False
        )
        batch_op.create_foreign_key(
            "fk_advance_employee_id",
            "employees",
            ["employee_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch_op.create_index("ix_advance_employee_month", ["employee_id", "request_month"], unique=False)

    op.create_index(
        "uq_advance_employee_month_open",
        "advance_requests",
        ["employee_id", "request_month"],
        unique=True,
        postgresql_where=sa.text("status IN ('pending', 'approved')"),
        sqlite_where=sa.text("status IN ('pending', 'approved')"),
    )

    with op.batch_alter_table("payslips", schema=None) as batch_op:
        batch_op.alter_column("employee_id", existing_type=sa.Integer(), nullable=False)
        batch_op.create_foreign_key(
            "fk_payslip_employee_id",
            "employees",
            ["employee_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch_op.create_index("ix_payslip_employee_month", ["employee_id", "month"], unique=False)
        batch_op.create_unique_constraint(
            "uq_payslip_employee_month", ["employee_id", "month"]
        )

    op.create_table(
        "admin_login_attempts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("ip", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_admin_login_attempts_ip",
        "admin_login_attempts",
        ["ip"],
        unique=False,
    )
    op.create_index(
        "ix_admin_login_attempt_ip_created",
        "admin_login_attempts",
        ["ip", "created_at"],
        unique=False,
    )


def downgrade():
    op.drop_index("ix_admin_login_attempt_ip_created", table_name="admin_login_attempts")
    op.drop_index("ix_admin_login_attempts_ip", table_name="admin_login_attempts")
    op.drop_table("admin_login_attempts")

    op.drop_index("uq_advance_employee_month_open", table_name="advance_requests")

    with op.batch_alter_table("payslips", schema=None) as batch_op:
        batch_op.drop_constraint("uq_payslip_employee_month", type_="unique")
        batch_op.drop_index("ix_payslip_employee_month")
        batch_op.drop_constraint("fk_payslip_employee_id", type_="foreignkey")
        batch_op.drop_column("holiday_pay")
        batch_op.drop_column("holiday_hours")
        batch_op.drop_column("employee_id")

    with op.batch_alter_table("advance_requests", schema=None) as batch_op:
        batch_op.drop_index("ix_advance_employee_month")
        batch_op.drop_constraint("fk_advance_employee_id", type_="foreignkey")
        batch_op.drop_column("employee_id")

    with op.batch_alter_table("attendance_records", schema=None) as batch_op:
        batch_op.drop_constraint("uq_attendance_employee_date", type_="unique")
        batch_op.drop_index("ix_attendance_employee_date")
        batch_op.drop_constraint("fk_attendance_employee_id", type_="foreignkey")
        batch_op.drop_column("employee_id")
