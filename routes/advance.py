import logging
import re
from datetime import datetime

from flask import (
    Blueprint,
    current_app,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from sqlalchemy.exc import IntegrityError

from models import AdvanceRequest, Employee, db

logger = logging.getLogger(__name__)

advance_bp = Blueprint("advance", __name__)

MONTH_PATTERN = re.compile(r"^\d{4}-\d{2}$")


def _validate_month(month: str) -> bool:
    if not MONTH_PATTERN.fullmatch(month or ""):
        return False
    year, mon = month.split("-")
    return 1 <= int(mon) <= 12 and int(year) >= 2000


@advance_bp.route("/advance", methods=["GET", "POST"])
def advance_page():
    cfg = current_app.config
    limit_weekly = int(cfg.get("ADVANCE_LIMIT_WEEKLY", 300_000))
    limit_shift = int(cfg.get("ADVANCE_LIMIT_SHIFT", 500_000))

    if request.method == "GET":
        return render_template(
            "advance.html", limit_weekly=limit_weekly, limit_shift=limit_shift
        )

    birth_date = request.form.get("birth_date", "").strip()
    emp_name = request.form.get("emp_name", "").strip()
    request_month = request.form.get("request_month", "").strip()
    amount_str = request.form.get("amount", "").strip()
    reason = request.form.get("reason", "").strip()

    errors = []
    if not re.fullmatch(r"\d{6}", birth_date):
        errors.append("생년월일은 YYMMDD 6자리 숫자여야 합니다.")
    if not emp_name:
        errors.append("이름을 입력해주세요.")
    if not _validate_month(request_month):
        errors.append("요청 월 형식이 올바르지 않습니다. (YYYY-MM)")

    employee = None
    if not errors:
        employee = Employee.query.filter_by(
            name=emp_name, birth_date=birth_date, is_active=True
        ).first()
        if not employee:
            errors.append("등록된 재직 직원만 가불 신청할 수 있습니다.")

    try:
        amount = int(amount_str)
    except (TypeError, ValueError):
        amount = 0
        errors.append("금액은 숫자여야 합니다.")

    if amount <= 0 and "금액은 숫자여야 합니다." not in errors:
        errors.append("금액은 0보다 커야 합니다.")

    work_type = employee.work_type if employee else "weekly"
    limit = limit_shift if work_type == "shift" else limit_weekly
    if amount > limit:
        errors.append(f"선택한 근무형태의 가불 한도({limit:,}원)를 초과했습니다.")

    if employee and request_month:
        dup = AdvanceRequest.query.filter(
            AdvanceRequest.employee_id == employee.id,
            AdvanceRequest.request_month == request_month,
            AdvanceRequest.status.in_(["pending", "approved"]),
        ).first()
        if dup:
            errors.append(f"{request_month}에 이미 처리 중/승인된 가불이 존재합니다.")

    if errors:
        return render_template(
            "advance.html",
            errors=errors,
            limit_weekly=limit_weekly,
            limit_shift=limit_shift,
            form=request.form,
        )

    try:
        request_item = AdvanceRequest(
            employee_id=employee.id,
            birth_date=employee.birth_date,
            emp_name=employee.name,
            dept="",
            work_type=employee.work_type,
            request_month=request_month,
            amount=amount,
            reason=reason,
        )
        db.session.add(request_item)
        db.session.commit()
        return render_template(
            "advance.html",
            success=True,
            limit_weekly=limit_weekly,
            limit_shift=limit_shift,
        )
    except IntegrityError:
        db.session.rollback()
        return render_template(
            "advance.html",
            errors=["같은 월의 중복 가불 신청이 차단되었습니다."],
            limit_weekly=limit_weekly,
            limit_shift=limit_shift,
            form=request.form,
        )
    except Exception as exc:
        db.session.rollback()
        logger.error("Advance create error: %s", exc)
        return render_template(
            "advance.html",
            errors=["서버 오류가 발생했습니다."],
            limit_weekly=limit_weekly,
            limit_shift=limit_shift,
            form=request.form,
        )


@advance_bp.route("/admin/advance")
def admin_advance():
    if not session.get("is_admin"):
        return redirect(url_for("auth.login"))

    month = request.args.get("month", "")
    status = request.args.get("status", "")

    query = AdvanceRequest.query
    if month and _validate_month(month):
        query = query.filter(AdvanceRequest.request_month == month)
    if status:
        query = query.filter(AdvanceRequest.status == status)

    items = query.order_by(AdvanceRequest.created_at.desc()).all()
    return render_template("admin_advance.html", items=items, month=month, filter_status=status)


@advance_bp.route("/admin/advance/<int:adv_id>/approve", methods=["POST"])
def approve_advance(adv_id):
    if not session.get("is_admin"):
        return jsonify({"error": "권한이 없습니다."}), 401

    try:
        adv = AdvanceRequest.query.get(adv_id)
        if not adv:
            return jsonify({"error": "가불 요청을 찾을 수 없습니다."}), 404
        if adv.status != "pending":
            return jsonify({"error": f"현재 상태({adv.status})에서는 승인할 수 없습니다."}), 400

        adv.status = "approved"
        adv.admin_comment = request.form.get("comment", "")
        adv.reviewed_at = datetime.now()
        db.session.commit()
        return jsonify({"success": True, "status": "approved"})
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "같은 월의 중복 승인 요청이 존재합니다."}), 409
    except Exception as exc:
        db.session.rollback()
        logger.error("Advance approve error: %s", exc)
        return jsonify({"error": "처리 중 오류가 발생했습니다."}), 500


@advance_bp.route("/admin/advance/<int:adv_id>/reject", methods=["POST"])
def reject_advance(adv_id):
    if not session.get("is_admin"):
        return jsonify({"error": "권한이 없습니다."}), 401

    try:
        adv = AdvanceRequest.query.get(adv_id)
        if not adv:
            return jsonify({"error": "가불 요청을 찾을 수 없습니다."}), 404
        if adv.status != "pending":
            return jsonify({"error": f"현재 상태({adv.status})에서는 반려할 수 없습니다."}), 400

        adv.status = "rejected"
        adv.admin_comment = request.form.get("comment", "")
        adv.reviewed_at = datetime.now()
        db.session.commit()
        return jsonify({"success": True, "status": "rejected"})
    except Exception as exc:
        db.session.rollback()
        logger.error("Advance reject error: %s", exc)
        return jsonify({"error": "처리 중 오류가 발생했습니다."}), 500
