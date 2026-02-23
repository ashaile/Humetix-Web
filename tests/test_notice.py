"""Tests for notice (announcement) feature."""

import json

from models import Announcement, db


def _login(client):
    with client.session_transaction() as sess:
        sess["is_admin"] = True


def _headers():
    return {"Content-Type": "application/json"}


# ── 퍼블릭 ──


def test_public_notices_page_loads(client, flask_app):
    resp = client.get("/notices")
    assert resp.status_code == 200
    assert "공지사항" in resp.data.decode("utf-8")


def test_public_notices_shows_public_only(client, flask_app):
    with flask_app.app_context():
        db.session.add(Announcement(title="공개글", content="내용1", category="public"))
        db.session.add(Announcement(title="내부글", content="내용2", category="internal"))
        db.session.commit()

    resp = client.get("/notices")
    body = resp.data.decode("utf-8")
    assert "공개글" in body
    assert "내부글" not in body


def test_public_notice_detail(client, flask_app):
    with flask_app.app_context():
        n = Announcement(title="상세보기", content="상세내용", category="public")
        db.session.add(n)
        db.session.commit()
        nid = n.id

    resp = client.get(f"/notices/{nid}")
    assert resp.status_code == 200
    body = resp.data.decode("utf-8")
    assert "상세보기" in body
    assert "상세내용" in body


def test_public_notice_detail_not_found(client, flask_app):
    resp = client.get("/notices/9999")
    assert resp.status_code == 404


def test_public_notice_detail_hides_internal(client, flask_app):
    with flask_app.app_context():
        n = Announcement(title="비공개", content="비공개내용", category="internal")
        db.session.add(n)
        db.session.commit()
        nid = n.id

    resp = client.get(f"/notices/{nid}")
    assert resp.status_code == 404


def test_check_new_notices_none(client, flask_app):
    resp = client.get("/api/notices/new?last_seen_id=0")
    data = resp.get_json()
    assert data["has_new"] is False


def test_check_new_notices_exists(client, flask_app):
    with flask_app.app_context():
        n = Announcement(title="새소식", content="내용", category="public")
        db.session.add(n)
        db.session.commit()
        nid = n.id

    resp = client.get("/api/notices/new?last_seen_id=0")
    data = resp.get_json()
    assert data["has_new"] is True
    assert data["latest_id"] == nid
    assert data["title"] == "새소식"


# ── 관리자 ──


def test_admin_notices_requires_admin(client, flask_app):
    resp = client.get("/admin/notices", follow_redirects=False)
    assert resp.status_code == 302


def test_admin_notices_loads(client, flask_app):
    _login(client)
    resp = client.get("/admin/notices")
    assert resp.status_code == 200
    assert "공지사항 관리" in resp.data.decode("utf-8")


def test_create_notice_success(client, flask_app):
    _login(client)
    resp = client.post("/api/notices",
        data=json.dumps({"title": "테스트공지", "content": "본문입니다"}),
        headers=_headers())
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["success"] is True
    assert data["notice"]["title"] == "테스트공지"


def test_create_notice_missing_title(client, flask_app):
    _login(client)
    resp = client.post("/api/notices",
        data=json.dumps({"title": "", "content": "본문"}),
        headers=_headers())
    assert resp.status_code == 400


def test_create_notice_missing_content(client, flask_app):
    _login(client)
    resp = client.post("/api/notices",
        data=json.dumps({"title": "제목", "content": ""}),
        headers=_headers())
    assert resp.status_code == 400


def test_update_notice(client, flask_app):
    _login(client)
    r = client.post("/api/notices",
        data=json.dumps({"title": "원제목", "content": "원내용"}),
        headers=_headers())
    nid = r.get_json()["notice"]["id"]

    resp = client.put(f"/api/notices/{nid}",
        data=json.dumps({"title": "수정제목", "is_pinned": True}),
        headers=_headers())
    data = resp.get_json()
    assert data["success"] is True
    assert data["notice"]["title"] == "수정제목"
    assert data["notice"]["is_pinned"] is True


def test_delete_notice(client, flask_app):
    _login(client)
    r = client.post("/api/notices",
        data=json.dumps({"title": "삭제공지", "content": "삭제될내용"}),
        headers=_headers())
    nid = r.get_json()["notice"]["id"]

    resp = client.delete(f"/api/notices/{nid}", headers=_headers())
    assert resp.get_json()["success"] is True


def test_create_notice_internal(client, flask_app):
    _login(client)
    resp = client.post("/api/notices",
        data=json.dumps({"title": "내부공지", "content": "내부내용", "category": "internal"}),
        headers=_headers())
    assert resp.status_code == 201
    assert resp.get_json()["notice"]["category"] == "internal"
