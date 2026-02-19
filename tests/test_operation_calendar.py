from datetime import date

from sqlalchemy import text

from models import AttendanceRecord, Employee, OperationCalendarDay, db
from routes.attendance import calc_work_hours


def test_calc_work_hours_respects_workday_override():
    cfg = {
        "BREAK_HOURS": 1.0,
        "STANDARD_WORK_HOURS": 8.0,
        "NIGHT_START": 22,
        "NIGHT_END": 6,
        "PUBLIC_HOLIDAYS_2026": ["2026-03-01"],
    }

    total, ot, _night, holiday = calc_work_hours(
        "09:00",
        "20:00",
        cfg,
        work_date=date(2026, 3, 1),
        calendar_day_type="workday",
    )

    assert total == 10.0
    assert ot == 2.0
    assert holiday == 0.0


def test_calc_work_hours_counts_unpaid_leave_as_holiday_work():
    cfg = {
        "BREAK_HOURS": 1.0,
        "STANDARD_WORK_HOURS": 8.0,
        "NIGHT_START": 22,
        "NIGHT_END": 6,
        "PUBLIC_HOLIDAYS_2026": [],
    }

    total, ot, _night, holiday = calc_work_hours(
        "09:00",
        "18:00",
        cfg,
        work_date=date(2026, 3, 7),
        calendar_day_type="unpaid_leave",
    )

    assert total == 8.0
    assert ot == 0.0
    assert holiday == 8.0


def test_create_attendance_uses_paid_leave_override(client):
    employee = Employee(
        name="tester",
        birth_date="900101",
        work_type="weekly",
        is_active=True,
    )
    db.session.add(employee)
    db.session.add(
        OperationCalendarDay(
            work_date=date(2026, 3, 4),
            day_type="paid_leave",
            note="test override",
        )
    )
    db.session.commit()

    response = client.post(
        "/api/attendance",
        json={
            "emp_name": "tester",
            "birth_date": "900101",
            "dept": "ops",
            "work_date": "2026-03-04",
            "work_type": "normal",
            "clock_in": "09:00",
            "clock_out": "18:00",
        },
    )

    assert response.status_code == 201
    payload = response.get_json()
    assert payload["record"]["holiday_work_hours"] == 8.0
    assert payload["record"]["overtime_hours"] == 0.0


def test_create_attendance_returns_503_when_calendar_table_missing(client):
    employee = Employee(
        name="tester_missing_table",
        birth_date="900101",
        work_type="weekly",
        is_active=True,
    )
    db.session.add(employee)
    db.session.commit()

    db.session.execute(text("DROP TABLE operation_calendar_days"))
    db.session.commit()

    response = client.post(
        "/api/attendance",
        json={
            "emp_name": "tester_missing_table",
            "birth_date": "900101",
            "dept": "ops",
            "work_date": "2026-03-05",
            "work_type": "normal",
            "clock_in": "09:00",
            "clock_out": "18:00",
        },
    )

    assert response.status_code == 503
    payload = response.get_json()
    assert "데이터베이스 초기화가 필요합니다." in payload["error"]


def test_update_attendance_returns_503_when_calendar_table_missing(client):
    employee = Employee(
        name="tester_update_missing_table",
        birth_date="900101",
        work_type="weekly",
        is_active=True,
    )
    db.session.add(employee)
    db.session.flush()

    record = AttendanceRecord(
        employee_id=employee.id,
        birth_date=employee.birth_date,
        emp_name=employee.name,
        dept="ops",
        work_date=date(2026, 3, 6),
        clock_in="09:00",
        clock_out="18:00",
        work_type="normal",
        total_work_hours=8.0,
        overtime_hours=0.0,
        night_hours=0.0,
        holiday_work_hours=0.0,
    )
    db.session.add(record)
    db.session.commit()

    db.session.execute(text("DROP TABLE operation_calendar_days"))
    db.session.commit()

    with client.session_transaction() as session_data:
        session_data["is_admin"] = True

    response = client.put(
        f"/api/attendance/{record.id}",
        json={
            "clock_in": "09:30",
            "clock_out": "18:30",
        },
    )

    assert response.status_code == 503
    payload = response.get_json()
    assert "데이터베이스 초기화가 필요합니다." in payload["error"]
