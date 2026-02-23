"""지원서 제출 및 문의 서버사이드 검증 테스트"""
from models import Application, db


def _submit(client, **overrides):
    data = {
        "name": "홍길동",
        "phone": "010-1234-5678",
        "agree": "on",
        "gender": "남",
        "birth": "1990-01-01",
        "address": "서울시",
        "shift": "주간",
        **overrides,
    }
    return client.post("/submit", data=data, follow_redirects=True)


def test_submit_missing_name_rejected(client, flask_app):
    """이름 없으면 거부"""
    resp = _submit(client, name="")
    assert resp.status_code == 200
    assert "이름과 연락처는 필수 항목입니다" in resp.data.decode("utf-8")
    with flask_app.app_context():
        assert Application.query.count() == 0


def test_submit_missing_phone_rejected(client, flask_app):
    """전화번호 없으면 거부"""
    resp = _submit(client, phone="")
    assert resp.status_code == 200
    assert "이름과 연락처는 필수 항목입니다" in resp.data.decode("utf-8")
    with flask_app.app_context():
        assert Application.query.count() == 0


def test_submit_no_agree_rejected(client, flask_app):
    """개인정보 미동의 시 거부"""
    resp = _submit(client, agree="")
    assert resp.status_code == 200
    assert "개인정보 수집·이용에 동의해주세요" in resp.data.decode("utf-8")
    with flask_app.app_context():
        assert Application.query.count() == 0


def test_submit_valid_saves_to_db(client, flask_app):
    """유효한 지원서는 DB에 저장됨"""
    with flask_app.app_context():
        before = Application.query.count()

    _submit(client)

    with flask_app.app_context():
        assert Application.query.count() == before + 1
        app = Application.query.first()
        assert app.name == "홍길동"
        assert app.agree is True


def test_contact_submit_missing_required(client, flask_app):
    """문의 폼 필수 항목 누락 시 거부"""
    resp = client.post("/contact_submit", data={"company": "", "name": "", "phone": ""})
    assert "필수 항목을 입력해주세요" in resp.data.decode("utf-8")


def test_security_headers_present(client, flask_app):
    """보안 헤더가 모든 응답에 포함되어야 함"""
    resp = client.get("/")
    assert resp.headers.get("X-Frame-Options") == "SAMEORIGIN"
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
