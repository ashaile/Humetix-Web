"""현장(사업장) 관리 블루프린트."""

import logging

from flask import Blueprint, jsonify, render_template, request
from sqlalchemy.exc import IntegrityError

from models import Employee, Site, db
from routes.utils import require_admin

logger = logging.getLogger(__name__)

site_bp = Blueprint("site", __name__)


@site_bp.route("/admin/sites")
@require_admin
def admin_sites():
    sites = Site.query.order_by(Site.name).all()
    unassigned = Employee.query.filter_by(is_active=True, site_id=None).count()
    employees = Employee.query.filter_by(is_active=True).order_by(Employee.name).all()
    return render_template(
        "admin_sites.html", sites=sites, unassigned=unassigned, employees=employees
    )


@site_bp.route("/api/sites", methods=["POST"])
@require_admin
def create_site():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "JSON body required"}), 400

    name = str(data.get("name", "")).strip()
    if not name:
        return jsonify({"error": "현장 이름을 입력해주세요."}), 400

    site = Site(
        name=name,
        address=str(data.get("address", "")).strip(),
        contact_person=str(data.get("contact_person", "")).strip(),
        contact_phone=str(data.get("contact_phone", "")).strip(),
    )
    try:
        db.session.add(site)
        db.session.commit()
        return jsonify({"success": True, "site": site.to_dict()}), 201
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": f"'{name}' 현장이 이미 등록되어 있습니다."}), 409


@site_bp.route("/api/sites/<int:site_id>", methods=["PUT"])
@require_admin
def update_site(site_id):
    site = db.session.get(Site, site_id)
    if not site:
        return jsonify({"error": "현장을 찾을 수 없습니다."}), 404

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "JSON body required"}), 400

    if "name" in data:
        name = str(data["name"]).strip()
        if not name:
            return jsonify({"error": "현장 이름은 비어 있을 수 없습니다."}), 400
        site.name = name
    if "address" in data:
        site.address = str(data["address"]).strip()
    if "contact_person" in data:
        site.contact_person = str(data["contact_person"]).strip()
    if "contact_phone" in data:
        site.contact_phone = str(data["contact_phone"]).strip()
    if "is_active" in data:
        site.is_active = bool(data["is_active"])

    try:
        db.session.commit()
        return jsonify({"success": True, "site": site.to_dict()})
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "현장명이 중복됩니다."}), 409


@site_bp.route("/api/sites/<int:site_id>", methods=["DELETE"])
@require_admin
def delete_site(site_id):
    site = db.session.get(Site, site_id)
    if not site:
        return jsonify({"error": "현장을 찾을 수 없습니다."}), 404

    assigned = Employee.query.filter_by(site_id=site_id).count()
    if assigned:
        return jsonify({"error": f"배정된 직원이 {assigned}명 있어 삭제할 수 없습니다."}), 409

    db.session.delete(site)
    db.session.commit()
    return jsonify({"success": True})


@site_bp.route("/api/sites/<int:site_id>/assign", methods=["POST"])
@require_admin
def assign_employees(site_id):
    site = db.session.get(Site, site_id)
    if not site:
        return jsonify({"error": "현장을 찾을 수 없습니다."}), 404

    data = request.get_json(silent=True)
    if not data or "employee_ids" not in data:
        return jsonify({"error": "employee_ids required"}), 400

    count = 0
    for eid in data["employee_ids"]:
        emp = db.session.get(Employee, eid)
        if emp:
            emp.site_id = site_id
            count += 1
    db.session.commit()
    return jsonify({"success": True, "assigned": count})


@site_bp.route("/api/sites/<int:site_id>/unassign", methods=["POST"])
@require_admin
def unassign_employees(site_id):
    data = request.get_json(silent=True)
    if not data or "employee_ids" not in data:
        return jsonify({"error": "employee_ids required"}), 400

    count = 0
    for eid in data["employee_ids"]:
        emp = db.session.get(Employee, eid)
        if emp and emp.site_id == site_id:
            emp.site_id = None
            count += 1
    db.session.commit()
    return jsonify({"success": True, "unassigned": count})
