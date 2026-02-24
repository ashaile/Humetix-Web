"""연차/퇴직금 관리 블루프린트 — 월별 발생/FIFO 사용 추적 포함."""

import logging
from datetime import date, datetime

from flask import Blueprint, jsonify, render_template, request
from sqlalchemy.orm import joinedload

from extensions import limiter
from models import Employee, LeaveAccrual, LeaveBalance, LeaveUsage, db
from routes.utils import require_admin
from services.leave_service import (
    calc_severance,
    delete_accrual,
    delete_usage,
    generate_accruals,
    get_employee_leave_detail,
    register_usage_fifo,
    sync_employees_to_leave,
    sync_leave_balances,
    sync_single_balance,
)

logger = logging.getLogger(__name__)

leave_bp = Blueprint("leave", __name__)


# ── 관리자: 연차 현황 목록 ──

@leave_bp.route("/admin/leave")
@require_admin
def admin_leave():
    """연차 현황 목록."""
    year = request.args.get("year", date.today().year, type=int)

    balances = (
        LeaveBalance.query
        .filter_by(year=year)
        .options(joinedload(LeaveBalance.employee))
        .all()
    )

    # 아직 연차관리에 등록되지 않은 활성 직원 목록
    synced_ids = {b.employee_id for b in balances}
    unsynced_employees = Employee.query.filter(
        Employee.is_active.is_(True),
    ).order_by(Employee.name).all()
    unsynced_employees = [e for e in unsynced_employees if e.id not in synced_ids]

    return render_template(
        "admin_leave.html",
        balances=balances,
        year=year,
        unsynced_employees=unsynced_employees,
    )


@leave_bp.route("/admin/leave/sync-employees", methods=["POST"])
@require_admin
def sync_employees():
    """활성 직원 전원을 연차관리에 등록."""
    year = request.form.get("year", date.today().year, type=int)
    added, already = sync_employees_to_leave(year)
    db.session.commit()
    return jsonify({
        "success": True,
        "added": added,
        "already": already,
        "message": f"신규 {added}명 등록, 기존 {already}명",
    })


@leave_bp.route("/admin/leave/sync", methods=["POST"])
@require_admin
def sync_leave():
    """전 직원 연차 일괄 동기화."""
    year = request.form.get("year", date.today().year, type=int)
    include_attendance = request.form.get("include_attendance", "1") == "1"
    synced, skipped, auto_created = sync_leave_balances(year, include_attendance)
    db.session.commit()
    parts = [f"{synced}명 동기화 완료"]
    if auto_created:
        parts.append(f"만근 자동발생 {auto_created}건")
    if not include_attendance:
        parts.append("(수동 데이터만)")
    return jsonify({
        "success": True,
        "synced": synced,
        "skipped": skipped,
        "auto_created": auto_created,
        "message": ", ".join(parts),
    })


@leave_bp.route("/api/leave/add-employee", methods=["POST"])
@require_admin
def add_employee_leave():
    """직원을 연차관리에 수동 추가."""
    data = request.get_json(silent=True) or {}
    emp_id = data.get("employee_id")
    year = int(data.get("year", date.today().year))
    entitled = float(data.get("entitled", 0))

    if not emp_id:
        return jsonify({"error": "직원을 선택해주세요."}), 400

    emp = db.session.get(Employee, int(emp_id))
    if not emp:
        return jsonify({"error": "직원을 찾을 수 없습니다."}), 404

    existing = LeaveBalance.query.filter_by(employee_id=emp.id, year=year).first()
    if existing:
        return jsonify({"error": f"{emp.name}은(는) 이미 {year}년 연차관리에 등록되어 있습니다."}), 409

    balance = LeaveBalance(
        employee_id=emp.id,
        year=year,
        entitled=entitled,
        used=0,
        remaining=entitled,
        carryover=0,
    )
    db.session.add(balance)

    # 발생일수가 있으면 Accrual에도 수동 등록
    if entitled > 0:
        accrual = LeaveAccrual(
            employee_id=emp.id,
            year=year,
            month=0,
            accrual_type="manual",
            days=entitled,
            remaining=entitled,
            description=f"관리자 수동 등록 ({entitled}일)",
        )
        db.session.add(accrual)
        db.session.flush()
        sync_single_balance(emp.id, year)

    db.session.commit()
    logger.info("직원 연차 수동 추가: %s %d년 %d일", emp.name, year, entitled)
    return jsonify({
        "success": True,
        "message": f"{emp.name}이(가) {year}년 연차관리에 추가되었습니다.",
        "data": balance.to_dict(),
    })


# ── 관리자: LeaveBalance 관리 (기존) ──

@leave_bp.route("/api/leave/<int:lid>", methods=["PUT"])
@require_admin
def update_leave(lid):
    """연차 잔액 수정 (발생/사용 일수)."""
    balance = db.session.get(LeaveBalance, lid)
    if not balance:
        return jsonify({"error": "연차 데이터를 찾을 수 없습니다."}), 404

    data = request.get_json(silent=True) or {}
    entitled = data.get("entitled")
    used = data.get("used")

    if entitled is not None:
        balance.entitled = float(entitled)
    if used is not None:
        balance.used = float(used)
    balance.remaining = max(balance.entitled + balance.carryover - balance.used, 0)

    db.session.commit()
    logger.info("연차 수정: id=%d, entitled=%.1f, used=%.1f, remaining=%.1f",
                lid, balance.entitled, balance.used, balance.remaining)
    return jsonify({
        "success": True,
        "message": "연차 정보가 수정되었습니다.",
        "data": balance.to_dict(),
    })


@leave_bp.route("/api/leave/<int:lid>", methods=["DELETE"])
@require_admin
def delete_leave(lid):
    """연차 잔액 삭제."""
    balance = db.session.get(LeaveBalance, lid)
    if not balance:
        return jsonify({"error": "연차 데이터를 찾을 수 없습니다."}), 404

    emp_name = balance.employee.name if balance.employee else "?"
    year = balance.year
    db.session.delete(balance)
    db.session.commit()
    logger.info("연차 삭제: %s %d년", emp_name, year)
    return jsonify({"success": True, "message": f"{emp_name}의 {year}년 연차 데이터가 삭제되었습니다."})


@leave_bp.route("/api/leave/bulk-delete", methods=["POST"])
@require_admin
def bulk_delete_leave():
    """연차 잔액 일괄 삭제."""
    data = request.get_json(silent=True) or {}
    ids = data.get("ids", [])

    if not ids:
        return jsonify({"error": "삭제할 항목을 선택해주세요."}), 400

    deleted = 0
    for lid in ids:
        balance = db.session.get(LeaveBalance, int(lid))
        if balance:
            db.session.delete(balance)
            deleted += 1

    db.session.commit()
    logger.info("연차 일괄 삭제: %d건", deleted)
    return jsonify({"success": True, "message": f"{deleted}건의 연차 데이터가 삭제되었습니다.", "deleted": deleted})


@leave_bp.route("/api/leave/recalc/<int:lid>", methods=["POST"])
@require_admin
def recalc_leave(lid):
    """연차 자동 재계산 (근로기준법 기준 + 근태기록 사용일)."""
    balance = db.session.get(LeaveBalance, lid)
    if not balance:
        return jsonify({"error": "연차 데이터를 찾을 수 없습니다."}), 404

    emp = balance.employee
    if not emp or not emp.hire_date:
        return jsonify({"error": "직원 입사일 정보가 없습니다."}), 400

    # Accrual 기반 동기화 (이월 포함 자동 계산)
    sync_single_balance(emp.id, balance.year)
    db.session.commit()

    # 갱신된 balance 다시 조회
    balance = LeaveBalance.query.filter_by(
        employee_id=emp.id, year=balance.year
    ).first()

    return jsonify({
        "success": True,
        "message": f"{emp.name}의 연차가 재계산되었습니다.",
        "data": balance.to_dict(),
    })


# ── 관리자: 직원별 연차 상세 ──

@leave_bp.route("/admin/leave/<int:emp_id>/detail")
@require_admin
def admin_leave_detail(emp_id):
    """직원별 연차 상세 페이지."""
    year = request.args.get("year", date.today().year, type=int)
    detail = get_employee_leave_detail(emp_id, year)
    if not detail:
        return "직원을 찾을 수 없습니다.", 404
    return render_template("admin_leave_detail.html", **detail)


# ── Accrual CRUD API ──

@leave_bp.route("/api/leave/accruals", methods=["POST"])
@require_admin
def create_accrual():
    """발생 추가 (관리자 수동)."""
    data = request.get_json(silent=True) or {}
    emp_id = data.get("employee_id")
    year = data.get("year")
    month = data.get("month")
    days = float(data.get("days", 1))
    desc = data.get("description", "")
    accrual_type = data.get("accrual_type", "manual")
    allowed_accrual_types = {"manual", "monthly", "annual_bulk", "auto_monthly"}
    if accrual_type not in allowed_accrual_types:
        accrual_type = "manual"

    if not emp_id or year is None or month is None:
        return jsonify({"error": "필수 항목이 누락되었습니다."}), 400

    existing = LeaveAccrual.query.filter_by(
        employee_id=emp_id, year=year, month=month
    ).first()
    if existing:
        return jsonify({"error": f"이미 {year}년 {month}월 발생 기록이 있습니다."}), 409

    accrual = LeaveAccrual(
        employee_id=emp_id,
        year=int(year),
        month=int(month),
        accrual_type=accrual_type,
        days=days,
        remaining=days,
        description=desc,
    )
    db.session.add(accrual)
    db.session.flush()
    sync_single_balance(emp_id, int(year))
    db.session.commit()

    return jsonify({"success": True, "message": "발생 기록이 추가되었습니다.", "data": accrual.to_dict()})


@leave_bp.route("/api/leave/accruals/<int:aid>", methods=["PUT"])
@require_admin
def update_accrual(aid):
    """발생 수정 (days, description)."""
    accrual = db.session.get(LeaveAccrual, aid)
    if not accrual:
        return jsonify({"error": "발생 기록을 찾을 수 없습니다."}), 404

    data = request.get_json(silent=True) or {}
    new_days = data.get("days")
    desc = data.get("description")

    if new_days is not None:
        new_days = float(new_days)
        used_from_this = accrual.days - accrual.remaining
        accrual.days = new_days
        accrual.remaining = max(new_days - used_from_this, 0)

    if desc is not None:
        accrual.description = desc

    db.session.flush()
    sync_single_balance(accrual.employee_id, accrual.year)
    db.session.commit()

    return jsonify({"success": True, "message": "발생 기록이 수정되었습니다.", "data": accrual.to_dict()})


@leave_bp.route("/api/leave/accruals/<int:aid>", methods=["DELETE"])
@require_admin
def remove_accrual(aid):
    """발생 삭제."""
    result = delete_accrual(aid)
    if "error" in result:
        return jsonify(result), 404
    db.session.commit()
    return jsonify(result)


# ── Usage CRUD API ──

@leave_bp.route("/api/leave/usages", methods=["POST"])
@require_admin
def create_usage():
    """사용 등록 (FIFO 자동 차감)."""
    data = request.get_json(silent=True) or {}
    emp_id = data.get("employee_id")
    use_date_str = data.get("use_date")
    days = float(data.get("days", 1))
    desc = data.get("description", "")

    if not emp_id or not use_date_str:
        return jsonify({"error": "필수 항목이 누락되었습니다."}), 400

    try:
        use_date = datetime.strptime(use_date_str, "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"error": "날짜 형식이 올바르지 않습니다 (YYYY-MM-DD)."}), 400

    usages = register_usage_fifo(emp_id, use_date, days, desc)
    db.session.commit()

    result_data = [u.to_dict() for u in usages]
    return jsonify({"success": True, "message": "사용이 등록되었습니다.", "data": result_data})


@leave_bp.route("/api/leave/usages/<int:uid>", methods=["DELETE"])
@require_admin
def remove_usage(uid):
    """사용 삭제 + 잔여 복원."""
    result = delete_usage(uid)
    if "error" in result:
        return jsonify(result), 404
    db.session.commit()
    return jsonify(result)


# ── 발생 자동 생성 ──

@leave_bp.route("/api/leave/<int:emp_id>/generate-accruals", methods=["POST"])
@require_admin
def api_generate_accruals(emp_id):
    """해당 직원의 발생 레코드 자동 생성."""
    data = request.get_json(silent=True) or request.form
    year = int(data.get("year", date.today().year))

    created = generate_accruals(emp_id, year)
    if created:
        sync_single_balance(emp_id, year)
    db.session.commit()

    return jsonify({
        "success": True,
        "created": created,
        "message": f"{created}건의 발생 기록이 생성되었습니다." if created else "추가할 발생 기록이 없습니다.",
    })


# ── 월 토글 (만근 체크/해제) ──

@leave_bp.route("/api/leave/accruals/toggle", methods=["POST"])
@require_admin
def toggle_monthly_accrual():
    """월별 만근 발생 토글 — 있으면 삭제, 없으면 생성."""
    data = request.get_json(silent=True) or {}
    emp_id = data.get("employee_id")
    year = int(data.get("year", date.today().year))
    month = int(data.get("month", 0))

    if not emp_id or not (1 <= month <= 12):
        return jsonify({"error": "잘못된 요청입니다."}), 400

    existing = LeaveAccrual.query.filter_by(
        employee_id=emp_id, year=year, month=month
    ).first()

    if existing:
        # 이미 사용된 발생분이면 삭제 불가
        used = existing.days - existing.remaining
        if used > 0:
            return jsonify({"error": f"이미 {used}일이 사용되어 해제할 수 없습니다."}), 400
        db.session.delete(existing)
        action = "off"
    else:
        accrual = LeaveAccrual(
            employee_id=emp_id,
            year=year,
            month=month,
            accrual_type="monthly",
            days=1,
            remaining=1,
            description=f"{month}월 만근 월차",
        )
        db.session.add(accrual)
        action = "on"

    db.session.flush()
    sync_single_balance(emp_id, year)
    db.session.commit()

    return jsonify({"success": True, "action": action, "month": month})


# ── 상세 → 연차관리 적용 (LeaveBalance 갱신) ──

@leave_bp.route("/api/leave/<int:emp_id>/apply", methods=["POST"])
@require_admin
def apply_leave_balance(emp_id):
    """상세 페이지 발생/사용 내역을 연차관리(LeaveBalance)에 적용."""
    data = request.get_json(silent=True) or request.form
    year = int(data.get("year", date.today().year))

    emp = db.session.get(Employee, emp_id)
    if not emp:
        return jsonify({"error": "직원을 찾을 수 없습니다."}), 404

    # 현재 발생/사용 내역 기준으로 LeaveBalance만 갱신 (재생성 없음)
    sync_single_balance(emp_id, year)
    db.session.commit()

    balance = LeaveBalance.query.filter_by(employee_id=emp_id, year=year).first()
    return jsonify({
        "success": True,
        "message": f"{emp.name}의 {year}년 연차가 연차관리에 적용되었습니다.",
        "data": balance.to_dict() if balance else None,
    })


# ── 관리자: 퇴직금 시뮬레이션 ──

@leave_bp.route("/admin/severance")
@require_admin
def admin_severance():
    """퇴직금 시뮬레이션 페이지."""
    employees = Employee.query.filter_by(is_active=True).order_by(Employee.name).all()
    return render_template("admin_severance.html", employees=employees)


@leave_bp.route("/api/severance/<int:emp_id>")
@require_admin
def api_severance(emp_id):
    """특정 직원 퇴직금 JSON."""
    result = calc_severance(emp_id)
    return jsonify(result)


# ── 공개: 직원 본인 연차 조회 ──

@leave_bp.route("/leave", methods=["GET", "POST"])
@limiter.limit("10 per minute")
def leave_lookup():
    """직원 본인 연차 조회 (이름 + 생년월일)."""
    if request.method == "GET":
        return render_template("leave_lookup.html")

    import re as _re
    name = request.form.get("name", "").strip()
    birth_date = request.form.get("birth_date", "").strip()

    if not name or not birth_date:
        return render_template(
            "leave_lookup.html", error="이름과 생년월일을 입력해주세요."
        )

    if not _re.fullmatch(r"\d{6}", birth_date):
        return render_template(
            "leave_lookup.html", error="생년월일은 6자리 숫자(YYMMDD)로 입력해주세요."
        )

    emp = Employee.query.filter_by(name=name, birth_date=birth_date, is_active=True).first()
    if not emp:
        return render_template(
            "leave_lookup.html", error="일치하는 직원 정보를 찾을 수 없습니다."
        )

    year = date.today().year
    balance = LeaveBalance.query.filter_by(employee_id=emp.id, year=year).first()

    return render_template(
        "leave_lookup.html",
        employee=emp,
        balance=balance,
        year=year,
    )
