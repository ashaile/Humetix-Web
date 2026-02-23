"""Tests for public payslip lookup feature."""

from models import Employee, Payslip, db


def _make_employee(flask_app, name="홍길동", birth="900101"):
    with flask_app.app_context():
        emp = Employee(name=name, birth_date=birth, is_active=True)
        db.session.add(emp)
        db.session.commit()
        return emp.id


def _make_payslip(flask_app, employee_id, month="2026-01"):
    with flask_app.app_context():
        ps = Payslip(
            employee_id=employee_id,
            emp_name="홍길동",
            dept="생산부",
            month=month,
            salary_mode="standard",
            total_work_hours=209,
            ot_hours=10,
            night_hours=5,
            holiday_hours=0,
            base_salary=2_156_880,
            ot_pay=154_800,
            night_pay=25_800,
            holiday_pay=0,
            gross=2_337_480,
            tax=77_137,
            insurance=226_736,
            advance_deduction=0,
            net=2_033_607,
        )
        db.session.add(ps)
        db.session.commit()
        return ps.id


def test_payslip_lookup_page_loads(client, flask_app):
    resp = client.get("/payslip")
    assert resp.status_code == 200
    assert "급여명세서 조회" in resp.data.decode("utf-8")


def test_payslip_lookup_invalid_birth_date(client, flask_app):
    resp = client.post("/payslip", data={
        "birth_date": "abc",
        "emp_name": "홍길동",
    })
    assert resp.status_code == 200
    assert "6자리" in resp.data.decode("utf-8")


def test_payslip_lookup_missing_name(client, flask_app):
    resp = client.post("/payslip", data={
        "birth_date": "900101",
        "emp_name": "",
    })
    assert resp.status_code == 200
    assert "이름" in resp.data.decode("utf-8")


def test_payslip_lookup_unregistered(client, flask_app):
    resp = client.post("/payslip", data={
        "birth_date": "900101",
        "emp_name": "없는사람",
    })
    assert resp.status_code == 200
    assert "재직 직원" in resp.data.decode("utf-8")


def test_payslip_lookup_no_payslips(client, flask_app):
    _make_employee(flask_app)
    resp = client.post("/payslip", data={
        "birth_date": "900101",
        "emp_name": "홍길동",
    })
    assert resp.status_code == 200
    body = resp.data.decode("utf-8")
    assert "홍길동" in body
    assert "0건" in body


def test_payslip_lookup_with_payslips(client, flask_app):
    emp_id = _make_employee(flask_app)
    _make_payslip(flask_app, emp_id)
    resp = client.post("/payslip", data={
        "birth_date": "900101",
        "emp_name": "홍길동",
    })
    assert resp.status_code == 200
    body = resp.data.decode("utf-8")
    assert "2026-01" in body
    assert "2,033,607" in body


def test_payslip_public_pdf_success(client, flask_app):
    emp_id = _make_employee(flask_app)
    _make_payslip(flask_app, emp_id)
    resp = client.get("/payslip/pdf?birth_date=900101&emp_name=홍길동&month=2026-01")
    assert resp.status_code == 200
    assert resp.content_type == "application/pdf"


def test_payslip_public_pdf_invalid_employee(client, flask_app):
    resp = client.get("/payslip/pdf?birth_date=900101&emp_name=없는사람&month=2026-01")
    assert resp.status_code == 403
