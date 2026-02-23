"""관리자 로그인 및 Rate Limit 테스트"""
from datetime import datetime, timedelta

import pytest

from models import AdminLoginAttempt, db


TEST_PASSWORD = "test_admin_password"


@pytest.fixture(autouse=True)
def patch_admin_password(monkeypatch):
    """_get_admin_password가 항상 테스트 비밀번호를 반환하도록 패치"""
    import routes.auth as auth_module
    monkeypatch.setattr(auth_module, "_get_admin_password", lambda: TEST_PASSWORD)


def _post_login(client, password):
    return client.post(
        "/login",
        data={"password": password},
        follow_redirects=True,
    )


def test_login_success(client, flask_app):
    """올바른 비밀번호로 로그인 시 세션이 생성되어야 함"""
    with client.session_transaction() as sess:
        assert not sess.get("is_admin")

    resp = _post_login(client, TEST_PASSWORD)
    assert resp.status_code == 200

    with client.session_transaction() as sess:
        assert sess.get("is_admin") is True


def test_login_failure_records_attempt(client, flask_app):
    """틀린 비밀번호로 로그인 시 DB에 시도 기록이 남아야 함"""
    with flask_app.app_context():
        before = AdminLoginAttempt.query.count()

    _post_login(client, "wrong_password")

    with flask_app.app_context():
        after = AdminLoginAttempt.query.count()

    assert after == before + 1


def test_login_blocked_after_max_attempts(client, flask_app):
    """5회 실패 후 로그인이 차단되어야 함"""
    for _ in range(5):
        _post_login(client, "wrong_password")

    resp = _post_login(client, TEST_PASSWORD)
    # 차단 시 올바른 비밀번호여도 세션 생성 안 됨
    with client.session_transaction() as sess:
        assert not sess.get("is_admin")
    assert "로그인 시도가 너무 많습니다" in resp.data.decode("utf-8")


def test_purge_expired_attempts(client, flask_app):
    """만료된 시도 레코드는 다음 로그인 요청 시 정리되어야 함"""
    with flask_app.app_context():
        # 만료된 레코드(10분 전) 직접 삽입
        old = AdminLoginAttempt(ip="1.2.3.4")
        old.created_at = datetime.now() - timedelta(minutes=10)
        db.session.add(old)
        db.session.commit()
        assert AdminLoginAttempt.query.count() == 1

    # 로그인 요청 1회 → purge 실행
    _post_login(client, "wrong_password")

    with flask_app.app_context():
        # 만료 레코드는 삭제되고 현재 실패 레코드 1개만 남아야 함
        remaining = AdminLoginAttempt.query.all()
        assert len(remaining) == 1
        assert remaining[0].ip != "1.2.3.4"


def test_logout_clears_session(client, flask_app):
    """로그아웃 시 세션이 초기화되어야 함"""
    _post_login(client, TEST_PASSWORD)

    with client.session_transaction() as sess:
        assert sess.get("is_admin")

    client.get("/logout")

    with client.session_transaction() as sess:
        assert not sess.get("is_admin")
