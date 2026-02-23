"""Tests for admin dashboard."""

from models import Employee, AttendanceRecord, Payslip, db
from datetime import date


def _login(client):
    with client.session_transaction() as sess:
        sess["is_admin"] = True


def test_dashboard_requires_admin(client, flask_app):
    resp = client.get("/admin/dashboard", follow_redirects=False)
    assert resp.status_code == 302
    assert "login" in resp.headers.get("Location", "")


def test_dashboard_loads(client, flask_app):
    _login(client)
    resp = client.get("/admin/dashboard")
    assert resp.status_code == 200
    assert "대시보드" in resp.data.decode("utf-8")


def test_dashboard_with_data(client, flask_app):
    _login(client)
    with flask_app.app_context():
        emp = Employee(name="테스트", birth_date="900101", is_active=True)
        db.session.add(emp)
        db.session.commit()

        att = AttendanceRecord(
            employee_id=emp.id, birth_date="900101", emp_name="테스트",
            work_date=date.today(), work_type="normal",
            total_work_hours=8, overtime_hours=1, night_hours=0, holiday_work_hours=0,
        )
        db.session.add(att)
        db.session.commit()

    resp = client.get("/admin/dashboard")
    assert resp.status_code == 200
    body = resp.data.decode("utf-8")
    assert "재직 중" in body


def test_dashboard_month_filter(client, flask_app):
    _login(client)
    resp = client.get("/admin/dashboard?month=2025-06")
    assert resp.status_code == 200
    assert "2025-06" in resp.data.decode("utf-8")
