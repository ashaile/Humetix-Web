"""관리자 전용 엔드포인트 인증 가드 회귀 테스트

모든 /admin/* 및 보호된 엔드포인트가 미로그인 시 로그인 페이지로
리다이렉트되는지 검증합니다. view_photo 취약점 재발 방지 포함.
"""
import pytest


# (method, url) 형태로 보호되어야 할 엔드포인트 목록
PROTECTED = [
    ("GET",  "/humetix_master_99"),
    ("GET",  "/download_excel"),
    ("POST", "/admin/change-password"),
    ("POST", "/update_memo/some-id"),
    ("POST", "/update_status/some-id"),
    ("GET",  "/inquiries"),
    ("POST", "/inquiries/delete"),
    ("POST", "/delete_selected"),
    ("GET",  "/view_photo/test.jpg"),   # 신분증 사진 — 인증 취약점 수정 회귀 방지
    ("POST", "/clear_data"),
    ("GET",  "/admin/attendance"),
    ("GET",  "/admin/attendance/excel"),
    ("GET",  "/admin/payslip"),
    ("POST", "/admin/payslip/generate"),
    ("GET",  "/admin/payslip/pdf"),
    ("GET",  "/admin/payslip/excel"),
    ("GET",  "/admin/employees"),
    ("GET",  "/admin/advance"),
    ("GET",  "/admin/dashboard"),
    ("GET",  "/admin/sites"),
    ("GET",  "/admin/notices"),
]


@pytest.mark.parametrize("method,url", PROTECTED)
def test_unauthenticated_redirects_to_login(client, flask_app, method, url):
    """비로그인 상태에서 보호된 엔드포인트 접근 시 로그인으로 리다이렉트"""
    if method == "GET":
        resp = client.get(url, follow_redirects=False)
    else:
        resp = client.post(url, follow_redirects=False)

    # 302 리다이렉트(/login 포함) 또는 401 Unauthorized — 둘 다 접근 거부
    assert resp.status_code in (302, 401), (
        f"{method} {url} → 기대: 302 또는 401, 실제: {resp.status_code}"
    )
    if resp.status_code == 302:
        location = resp.headers.get("Location", "")
        assert "login" in location, (
            f"{method} {url} → Location에 'login' 없음: {location!r}"
        )
