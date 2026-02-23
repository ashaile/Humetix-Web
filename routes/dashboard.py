"""관리자 종합 대시보드 블루프린트."""

import logging
from datetime import date, datetime

from flask import Blueprint, render_template, request
from sqlalchemy import func

from models import (
    AdvanceRequest,
    Application,
    AttendanceRecord,
    Employee,
    Payslip,
    Site,
    db,
)
from routes.utils import require_admin

logger = logging.getLogger(__name__)

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/admin/dashboard")
@require_admin
def admin_dashboard():
    today = date.today()
    current_month = today.strftime("%Y-%m")
    selected_month = request.args.get("month", current_month)

    # ── 재직자 현황 ──
    emp_active = Employee.query.filter_by(is_active=True).count()
    emp_inactive = Employee.query.filter_by(is_active=False).count()
    emp_weekly = Employee.query.filter_by(is_active=True, work_type="weekly").count()
    emp_shift = Employee.query.filter_by(is_active=True, work_type="shift").count()

    # ── 월별 근태 ──
    try:
        month_start = datetime.strptime(f"{selected_month}-01", "%Y-%m-%d").date()
    except ValueError:
        month_start = datetime.strptime(f"{current_month}-01", "%Y-%m-%d").date()
        selected_month = current_month

    if month_start.month == 12:
        month_end = date(month_start.year + 1, 1, 1)
    else:
        month_end = date(month_start.year, month_start.month + 1, 1)

    att = db.session.query(
        func.count(AttendanceRecord.id),
        func.coalesce(func.sum(AttendanceRecord.total_work_hours), 0),
        func.coalesce(func.sum(AttendanceRecord.overtime_hours), 0),
        func.coalesce(func.sum(AttendanceRecord.night_hours), 0),
        func.coalesce(func.sum(AttendanceRecord.holiday_work_hours), 0),
    ).filter(
        AttendanceRecord.work_date >= month_start,
        AttendanceRecord.work_date < month_end,
    ).first()

    att_workers = db.session.query(
        func.count(func.distinct(AttendanceRecord.employee_id))
    ).filter(
        AttendanceRecord.work_date >= month_start,
        AttendanceRecord.work_date < month_end,
    ).scalar() or 0

    # ── 급여 현황 ──
    pay = db.session.query(
        func.count(Payslip.id),
        func.coalesce(func.sum(Payslip.gross), 0),
        func.coalesce(func.sum(Payslip.net), 0),
        func.coalesce(func.avg(Payslip.net), 0),
    ).filter(Payslip.month == selected_month).first()

    # ── 가불 현황 ──
    adv_pending = AdvanceRequest.query.filter_by(status="pending").count()
    adv_approved = AdvanceRequest.query.filter(
        AdvanceRequest.status == "approved",
        AdvanceRequest.request_month == selected_month,
    ).count()
    adv_rejected = AdvanceRequest.query.filter(
        AdvanceRequest.status == "rejected",
        AdvanceRequest.request_month == selected_month,
    ).count()
    adv_amount = db.session.query(
        func.coalesce(func.sum(AdvanceRequest.amount), 0)
    ).filter(
        AdvanceRequest.status == "approved",
        AdvanceRequest.request_month == selected_month,
    ).scalar()

    # ── 현장별 인원 ──
    site_stats = db.session.query(
        Site.id, Site.name,
        func.count(Employee.id),
    ).outerjoin(Employee, db.and_(
        Employee.site_id == Site.id,
        Employee.is_active.is_(True),
    )).filter(Site.is_active.is_(True)).group_by(Site.id, Site.name).all()

    unassigned = Employee.query.filter(
        Employee.is_active.is_(True),
        Employee.site_id.is_(None),
    ).count()

    # ── 최근 입사지원 ──
    recent_apps = Application.query.order_by(
        Application.timestamp.desc()
    ).limit(5).all()

    stats = {
        "employees": {
            "active": emp_active,
            "inactive": emp_inactive,
            "weekly": emp_weekly,
            "shift": emp_shift,
        },
        "attendance": {
            "records": att[0] or 0,
            "total_hours": round(float(att[1]), 1),
            "ot_hours": round(float(att[2]), 1),
            "night_hours": round(float(att[3]), 1),
            "holiday_hours": round(float(att[4]), 1),
            "workers": att_workers,
        },
        "payslip": {
            "count": pay[0] or 0,
            "total_gross": int(pay[1]),
            "total_net": int(pay[2]),
            "avg_net": round(float(pay[3])),
        },
        "advance": {
            "pending": adv_pending,
            "approved": adv_approved,
            "rejected": adv_rejected,
            "total_amount": int(adv_amount),
        },
    }

    return render_template(
        "admin_dashboard.html",
        stats=stats,
        month=selected_month,
        recent_apps=recent_apps,
        site_stats=site_stats,
        unassigned=unassigned,
    )
