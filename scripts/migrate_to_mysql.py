"""
SQLite -> MySQL 일회성 데이터 이관 스크립트

사전 조건:
  1. MySQL에 humetix DB 생성 완료
  2. .env에 DATABASE_URL 설정 완료
  3. flask db upgrade 로 테이블 생성 완료

사용법:
  python scripts/migrate_to_mysql.py [sqlite_path]

기본 SQLite 경로: /var/www/recruit/humetix.db
"""
import os
import sys
import sqlite3
from datetime import datetime, date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from models import (
    db,
    Application,
    Career,
    Inquiry,
    Employee,
    AttendanceRecord,
    OperationCalendarDay,
    Payslip,
    AdvanceRequest,
    AdminLoginAttempt,
)

DEFAULT_SQLITE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "humetix.db"
)


def _parse_date(val):
    """SQLite 날짜 문자열을 Python date로 변환"""
    if not val:
        return None
    try:
        return datetime.strptime(val, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _parse_datetime(val):
    """SQLite datetime 문자열을 Python datetime으로 변환"""
    if not val:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f"):
        try:
            return datetime.strptime(val, fmt)
        except (ValueError, TypeError):
            continue
    return None


def _bool(val):
    """SQLite 0/1을 Python bool로 변환"""
    if val is None:
        return None
    return bool(val)


def migrate(sqlite_path):
    conn = sqlite3.connect(sqlite_path)
    conn.row_factory = sqlite3.Row

    with app.app_context():
        # ── 1. 독립 테이블 ──

        # applications
        rows = conn.execute("SELECT * FROM applications").fetchall()
        for r in rows:
            obj = Application(
                id=r["id"],
                timestamp=_parse_datetime(r["timestamp"]),
                updated_at=_parse_datetime(r["updated_at"]),
                photo=r["photo"],
                name=r["name"],
                birth=_parse_date(r["birth"]),
                phone=r["phone"],
                email=r["email"],
                gender=r["gender"],
                address=r["address"],
                height=r["height"],
                weight=r["weight"],
                vision=r["vision"],
                shoes=r["shoes"],
                tshirt=r["tshirt"],
                shift=r["shift"],
                posture=r["posture"],
                overtime=r["overtime"],
                holiday=r["holiday"],
                interview_date=_parse_date(r["interview_date"]),
                start_date=_parse_date(r["start_date"]),
                agree=_bool(r["agree"]),
                advance_pay=r["advance_pay"],
                insurance_type=r["insurance_type"],
                memo=r["memo"],
                status=r["status"],
            )
            db.session.add(obj)
        db.session.flush()
        print(f"  applications: {len(rows)}건")

        # employees
        rows = conn.execute("SELECT * FROM employees").fetchall()
        for r in rows:
            obj = Employee(
                id=r["id"],
                name=r["name"],
                birth_date=r["birth_date"],
                work_type=r["work_type"],
                hire_date=_parse_date(r["hire_date"]),
                resign_date=_parse_date(r["resign_date"]),
                is_active=_bool(r["is_active"]),
                created_at=_parse_datetime(r["created_at"]),
                updated_at=_parse_datetime(r["updated_at"]),
            )
            db.session.add(obj)
        db.session.flush()
        print(f"  employees: {len(rows)}건")

        # inquiries
        rows = conn.execute("SELECT * FROM inquiries").fetchall()
        for r in rows:
            obj = Inquiry(
                id=r["id"],
                created_at=_parse_datetime(r["created_at"]),
                updated_at=_parse_datetime(r["updated_at"]),
                company=r["company"],
                name=r["name"],
                phone=r["phone"],
                email=r["email"],
                message=r["message"],
                status=r["status"],
                assignee=r["assignee"],
                admin_memo=r["admin_memo"],
            )
            db.session.add(obj)
        db.session.flush()
        print(f"  inquiries: {len(rows)}건")

        # operation_calendar_days
        rows = conn.execute("SELECT * FROM operation_calendar_days").fetchall()
        for r in rows:
            obj = OperationCalendarDay(
                id=r["id"],
                work_date=_parse_date(r["work_date"]),
                day_type=r["day_type"],
                note=r["note"],
                created_at=_parse_datetime(r["created_at"]),
                updated_at=_parse_datetime(r["updated_at"]),
            )
            db.session.add(obj)
        db.session.flush()
        print(f"  operation_calendar_days: {len(rows)}건")

        # admin_login_attempts
        rows = conn.execute("SELECT * FROM admin_login_attempts").fetchall()
        for r in rows:
            obj = AdminLoginAttempt(
                id=r["id"],
                ip=r["ip"],
                created_at=_parse_datetime(r["created_at"]),
            )
            db.session.add(obj)
        db.session.flush()
        print(f"  admin_login_attempts: {len(rows)}건")

        # ── 2. FK 의존 테이블 ──

        # careers (-> applications)
        rows = conn.execute("SELECT * FROM careers").fetchall()
        for r in rows:
            obj = Career(
                id=r["id"],
                application_id=r["application_id"],
                company=r["company"],
                start=_parse_date(r["start"]),
                end=_parse_date(r["end"]),
                role=r["role"],
                reason=r["reason"],
            )
            db.session.add(obj)
        db.session.flush()
        print(f"  careers: {len(rows)}건")

        # attendance_records (-> employees)
        rows = conn.execute("SELECT * FROM attendance_records").fetchall()
        for r in rows:
            obj = AttendanceRecord(
                id=r["id"],
                employee_id=r["employee_id"],
                birth_date=r["birth_date"],
                emp_name=r["emp_name"],
                dept=r["dept"],
                work_date=_parse_date(r["work_date"]),
                clock_in=r["clock_in"],
                clock_out=r["clock_out"],
                work_type=r["work_type"],
                total_work_hours=r["total_work_hours"] or 0.0,
                overtime_hours=r["overtime_hours"] or 0.0,
                night_hours=r["night_hours"] or 0.0,
                holiday_work_hours=r["holiday_work_hours"] or 0.0,
                created_at=_parse_datetime(r["created_at"]),
                updated_at=_parse_datetime(r["updated_at"]),
            )
            db.session.add(obj)
        db.session.flush()
        print(f"  attendance_records: {len(rows)}건")

        # payslips (-> employees)
        rows = conn.execute("SELECT * FROM payslips").fetchall()
        for r in rows:
            obj = Payslip(
                id=r["id"],
                employee_id=r["employee_id"],
                emp_name=r["emp_name"],
                dept=r["dept"],
                month=r["month"],
                salary_mode=r["salary_mode"],
                total_work_hours=r["total_work_hours"] or 0.0,
                ot_hours=r["ot_hours"] or 0.0,
                night_hours=r["night_hours"] or 0.0,
                holiday_hours=r["holiday_hours"] or 0.0,
                base_salary=r["base_salary"] or 0,
                ot_pay=r["ot_pay"] or 0,
                night_pay=r["night_pay"] or 0,
                holiday_pay=r["holiday_pay"] or 0,
                gross=r["gross"] or 0,
                tax=r["tax"] or 0,
                insurance=r["insurance"] or 0,
                advance_deduction=r["advance_deduction"] or 0,
                net=r["net"] or 0,
                created_at=_parse_datetime(r["created_at"]),
                updated_at=_parse_datetime(r["updated_at"]),
            )
            db.session.add(obj)
        db.session.flush()
        print(f"  payslips: {len(rows)}건")

        # advance_requests (-> employees)
        rows = conn.execute("SELECT * FROM advance_requests").fetchall()
        for r in rows:
            obj = AdvanceRequest(
                id=r["id"],
                employee_id=r["employee_id"],
                birth_date=r["birth_date"],
                emp_name=r["emp_name"],
                dept=r["dept"],
                request_month=r["request_month"],
                work_type=r["work_type"],
                amount=r["amount"],
                reason=r["reason"],
                status=r["status"],
                admin_comment=r["admin_comment"],
                created_at=_parse_datetime(r["created_at"]),
                reviewed_at=_parse_datetime(r["reviewed_at"]),
                updated_at=_parse_datetime(r["updated_at"]),
            )
            db.session.add(obj)
        db.session.flush()
        print(f"  advance_requests: {len(rows)}건")

        # ── 3. 커밋 ──
        db.session.commit()
        print("\n데이터 이관 완료!")

        # ── 4. 검증 ──
        print("\n행 수 검증:")
        tables = [
            ("applications", Application),
            ("careers", Career),
            ("inquiries", Inquiry),
            ("employees", Employee),
            ("attendance_records", AttendanceRecord),
            ("operation_calendar_days", OperationCalendarDay),
            ("payslips", Payslip),
            ("advance_requests", AdvanceRequest),
            ("admin_login_attempts", AdminLoginAttempt),
        ]
        all_ok = True
        for table_name, Model in tables:
            sqlite_count = conn.execute(
                f"SELECT COUNT(*) FROM {table_name}"
            ).fetchone()[0]
            mysql_count = Model.query.count()
            status = "OK" if sqlite_count == mysql_count else "MISMATCH"
            if status == "MISMATCH":
                all_ok = False
            print(f"  {table_name}: SQLite={sqlite_count}, MySQL={mysql_count} [{status}]")

        conn.close()

        if all_ok:
            print("\n모든 테이블 검증 통과!")
        else:
            print("\n경고: 일부 테이블에서 행 수 불일치 발견!")
            sys.exit(1)


if __name__ == "__main__":
    sqlite_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SQLITE_PATH
    if not os.path.exists(sqlite_path):
        print(f"SQLite 파일을 찾을 수 없습니다: {sqlite_path}")
        sys.exit(1)
    print(f"SQLite 경로: {sqlite_path}")
    print(f"MySQL 대상: {app.config['SQLALCHEMY_DATABASE_URI'][:50]}...")
    print()
    migrate(sqlite_path)
