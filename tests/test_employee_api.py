"""직원 API CRUD 및 유효성 검사 테스트"""
import json
import pytest
from models import Employee, db


def _login(client):
    with client.session_transaction() as sess:
        sess["is_admin"] = True


def _post_employee(client, **overrides):
    data = {"name": "이영희", "birth_date": "950315", "work_type": "weekly", **overrides}
    return client.post(
        "/api/employees",
        data=json.dumps(data),
        content_type="application/json",
    )


# ── 생성 ──────────────────────────────────────────────

def test_create_employee_success(client, flask_app):
    """정상 직원 생성 → 201 + DB 저장"""
    _login(client)
    resp = _post_employee(client)
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["success"] is True
    assert data["employee"]["name"] == "이영희"

    with flask_app.app_context():
        assert Employee.query.filter_by(name="이영희").count() == 1


def test_create_employee_missing_name(client, flask_app):
    """이름 누락 → 400"""
    _login(client)
    resp = _post_employee(client, name="")
    assert resp.status_code == 400


def test_create_employee_invalid_birth_date(client, flask_app):
    """생년월일 형식 오류 → 400"""
    _login(client)
    resp = _post_employee(client, birth_date="19950315")
    assert resp.status_code == 400


def test_create_employee_invalid_work_type(client, flask_app):
    """잘못된 work_type → 400"""
    _login(client)
    resp = _post_employee(client, work_type="unknown")
    assert resp.status_code == 400


def test_create_employee_duplicate_rejected(client, flask_app):
    """동명이인 + 동일 생년월일 중복 등록 → 409"""
    _login(client)
    _post_employee(client)
    resp = _post_employee(client)  # 동일 데이터 재등록
    assert resp.status_code == 409


def test_create_employee_requires_admin(client, flask_app):
    """미로그인 시 401"""
    resp = _post_employee(client)
    assert resp.status_code == 401


# ── 수정 ──────────────────────────────────────────────

def test_update_employee_work_type(client, flask_app):
    """work_type 변경 → 반영 확인"""
    _login(client)
    _post_employee(client)

    with flask_app.app_context():
        emp = Employee.query.filter_by(name="이영희").first()
        emp_id = emp.id

    resp = client.put(
        f"/api/employees/{emp_id}",
        data=json.dumps({"work_type": "shift"}),
        content_type="application/json",
    )
    assert resp.status_code == 200
    assert resp.get_json()["employee"]["work_type"] == "shift"


def test_update_employee_not_found(client, flask_app):
    """존재하지 않는 직원 수정 → 404"""
    _login(client)
    resp = client.put(
        "/api/employees/99999",
        data=json.dumps({"work_type": "shift"}),
        content_type="application/json",
    )
    assert resp.status_code == 404


# ── 삭제 ──────────────────────────────────────────────

def test_delete_employee_success(client, flask_app):
    """연결 데이터 없는 직원 삭제 → 성공"""
    _login(client)
    _post_employee(client)

    with flask_app.app_context():
        emp_id = Employee.query.filter_by(name="이영희").first().id

    resp = client.delete(f"/api/employees/{emp_id}")
    assert resp.status_code == 200
    with flask_app.app_context():
        assert db.session.get(Employee, emp_id) is None


def test_delete_employee_not_found(client, flask_app):
    """존재하지 않는 직원 삭제 → 404"""
    _login(client)
    resp = client.delete("/api/employees/99999")
    assert resp.status_code == 404


# ── 검증 ──────────────────────────────────────────────

def test_verify_employee_success(client, flask_app):
    """등록된 직원 검증 → verified: true"""
    _login(client)
    _post_employee(client)

    resp = client.post(
        "/api/employees/verify",
        data=json.dumps({"name": "이영희", "birth_date": "950315"}),
        content_type="application/json",
    )
    data = resp.get_json()
    assert data["verified"] is True
    assert data["employee"]["name"] == "이영희"


def test_verify_employee_not_found(client, flask_app):
    """미등록 직원 검증 → verified: false"""
    resp = client.post(
        "/api/employees/verify",
        data=json.dumps({"name": "없는사람", "birth_date": "000101"}),
        content_type="application/json",
    )
    assert resp.get_json()["verified"] is False


def test_verify_inactive_employee_rejected(client, flask_app):
    """퇴사 처리된 직원은 검증 실패"""
    _login(client)
    _post_employee(client)

    with flask_app.app_context():
        emp = Employee.query.filter_by(name="이영희").first()
        emp.is_active = False
        db.session.commit()

    resp = client.post(
        "/api/employees/verify",
        data=json.dumps({"name": "이영희", "birth_date": "950315"}),
        content_type="application/json",
    )
    assert resp.get_json()["verified"] is False
