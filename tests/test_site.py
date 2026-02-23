"""Tests for site management feature."""

import json

from models import Employee, Site, db


def _login(client):
    with client.session_transaction() as sess:
        sess["is_admin"] = True


def _headers():
    return {"Content-Type": "application/json"}


def test_admin_sites_requires_admin(client, flask_app):
    resp = client.get("/admin/sites", follow_redirects=False)
    assert resp.status_code == 302


def test_admin_sites_loads(client, flask_app):
    _login(client)
    resp = client.get("/admin/sites")
    assert resp.status_code == 200
    assert "현장 관리" in resp.data.decode("utf-8")


def test_create_site_success(client, flask_app):
    _login(client)
    resp = client.post("/api/sites",
        data=json.dumps({"name": "A공장", "address": "서울시"}),
        headers=_headers())
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["success"] is True
    assert data["site"]["name"] == "A공장"


def test_create_site_duplicate(client, flask_app):
    _login(client)
    client.post("/api/sites",
        data=json.dumps({"name": "A공장"}),
        headers=_headers())
    resp = client.post("/api/sites",
        data=json.dumps({"name": "A공장"}),
        headers=_headers())
    assert resp.status_code == 409


def test_create_site_missing_name(client, flask_app):
    _login(client)
    resp = client.post("/api/sites",
        data=json.dumps({"name": ""}),
        headers=_headers())
    assert resp.status_code == 400


def test_update_site(client, flask_app):
    _login(client)
    r = client.post("/api/sites",
        data=json.dumps({"name": "B공장"}),
        headers=_headers())
    sid = r.get_json()["site"]["id"]
    resp = client.put(f"/api/sites/{sid}",
        data=json.dumps({"address": "부산시"}),
        headers=_headers())
    assert resp.get_json()["success"] is True


def test_delete_site_success(client, flask_app):
    _login(client)
    r = client.post("/api/sites",
        data=json.dumps({"name": "C공장"}),
        headers=_headers())
    sid = r.get_json()["site"]["id"]
    resp = client.delete(f"/api/sites/{sid}", headers=_headers())
    assert resp.get_json()["success"] is True


def test_delete_site_with_employees(client, flask_app):
    _login(client)
    r = client.post("/api/sites",
        data=json.dumps({"name": "D공장"}),
        headers=_headers())
    sid = r.get_json()["site"]["id"]

    with flask_app.app_context():
        emp = Employee(name="직원", birth_date="900101", site_id=sid, is_active=True)
        db.session.add(emp)
        db.session.commit()

    resp = client.delete(f"/api/sites/{sid}", headers=_headers())
    assert resp.status_code == 409
    assert "배정된 직원" in resp.get_json()["error"]


def test_assign_employees(client, flask_app):
    _login(client)
    r = client.post("/api/sites",
        data=json.dumps({"name": "E공장"}),
        headers=_headers())
    sid = r.get_json()["site"]["id"]

    with flask_app.app_context():
        emp = Employee(name="직원2", birth_date="910101", is_active=True)
        db.session.add(emp)
        db.session.commit()
        eid = emp.id

    resp = client.post(f"/api/sites/{sid}/assign",
        data=json.dumps({"employee_ids": [eid]}),
        headers=_headers())
    data = resp.get_json()
    assert data["success"] is True
    assert data["assigned"] == 1


def test_unassign_employees(client, flask_app):
    _login(client)
    with flask_app.app_context():
        site = Site(name="F공장")
        db.session.add(site)
        db.session.flush()
        emp = Employee(name="직원3", birth_date="920101", site_id=site.id, is_active=True)
        db.session.add(emp)
        db.session.commit()
        sid, eid = site.id, emp.id

    resp = client.post(f"/api/sites/{sid}/unassign",
        data=json.dumps({"employee_ids": [eid]}),
        headers=_headers())
    data = resp.get_json()
    assert data["success"] is True
    assert data["unassigned"] == 1
