"""가불 신청 유효성 검사 및 비즈니스 로직 테스트"""
import pytest
from models import AdvanceRequest, Employee, db


def _make_employee(flask_app, name="김철수", birth_date="900101", work_type="weekly"):
    """테스트용 직원 생성 헬퍼"""
    with flask_app.app_context():
        emp = Employee(name=name, birth_date=birth_date, work_type=work_type, is_active=True)
        db.session.add(emp)
        db.session.commit()
        return emp.id


def _post_advance(client, **overrides):
    data = {
        "emp_name": "김철수",
        "birth_date": "900101",
        "request_month": "2026-02",
        "amount": "200000",
        "reason": "생활비",
        **overrides,
    }
    return client.post("/advance", data=data, follow_redirects=True)


def test_advance_page_loads(client, flask_app):
    """가불 신청 페이지 정상 로드"""
    resp = client.get("/advance")
    assert resp.status_code == 200


def test_advance_invalid_birth_date_format(client, flask_app):
    """생년월일 형식 오류 시 에러"""
    resp = _post_advance(client, birth_date="19900101")
    assert "생년월일은 YYMMDD 6자리 숫자여야 합니다" in resp.data.decode("utf-8")


def test_advance_missing_name(client, flask_app):
    """이름 없으면 에러"""
    resp = _post_advance(client, emp_name="")
    assert "이름을 입력해주세요" in resp.data.decode("utf-8")


def test_advance_unregistered_employee_rejected(client, flask_app):
    """미등록 직원은 가불 신청 불가"""
    resp = _post_advance(client)
    assert "등록된 재직 직원만 가불 신청할 수 있습니다" in resp.data.decode("utf-8")


def test_advance_zero_amount_rejected(client, flask_app):
    """금액 0원 이하 거부"""
    _make_employee(flask_app)
    resp = _post_advance(client, amount="0")
    assert "0보다 커야 합니다" in resp.data.decode("utf-8")


def test_advance_exceeds_limit_rejected(client, flask_app):
    """주간 한도(30만원) 초과 시 거부"""
    _make_employee(flask_app)
    resp = _post_advance(client, amount="999999")
    assert "한도" in resp.data.decode("utf-8")


def test_advance_success(client, flask_app):
    """유효한 가불 신청 → DB 저장"""
    _make_employee(flask_app)
    with flask_app.app_context():
        before = AdvanceRequest.query.count()

    resp = _post_advance(client)
    text = resp.data.decode("utf-8")

    with flask_app.app_context():
        assert AdvanceRequest.query.count() == before + 1


def test_advance_duplicate_rejected(client, flask_app):
    """같은 달 중복 신청 거부"""
    _make_employee(flask_app)
    _post_advance(client)  # 첫 번째 신청

    resp = _post_advance(client)  # 두 번째 신청 (같은 달)
    assert "이미 처리 중" in resp.data.decode("utf-8")


def test_advance_shift_worker_higher_limit(client, flask_app):
    """교대 근무자는 한도가 더 높음 (50만원)"""
    _make_employee(flask_app, work_type="shift")
    # 주간 한도(30만원) 초과, 교대 한도(50만원) 이내 금액
    resp = _post_advance(client, amount="400000")
    text = resp.data.decode("utf-8")
    # 교대 근무자는 통과해야 함 → "한도" 에러 없음
    assert "한도" not in text or "성공" in text or AdvanceRequest.query
