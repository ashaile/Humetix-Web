"""급여 계산 비즈니스 로직 (payslip 라우트에서 추출)"""
from datetime import datetime

from flask import current_app
from sqlalchemy import func

from models import AdvanceRequest, AttendanceRecord, Payslip, db

ALLOWED_SALARY_MODES = {"standard", "actual"}


def _month_range(month: str):
    month_start = f"{month}-01"
    year, mon = month.split("-")
    if int(mon) == 12:
        month_end = f"{int(year) + 1}-01-01"
    else:
        month_end = f"{year}-{int(mon) + 1:02d}-01"
    return (
        datetime.strptime(month_start, "%Y-%m-%d").date(),
        datetime.strptime(month_end, "%Y-%m-%d").date(),
    )


def compute_payslips(month: str, salary_mode: str):
    """월별 급여를 계산하고 DB에 저장한다.

    Returns (created, updated) 또는 error 문자열.
    """
    cfg = current_app.config
    hourly = cfg.get("HOURLY_WAGE", 10320)
    std_monthly_hours = cfg.get("MONTHLY_STANDARD_HOURS", 209)
    ot_mult = cfg.get("OT_MULTIPLIER", 1.5)
    night_prem = cfg.get("NIGHT_PREMIUM", 0.5)
    tax_rate = cfg.get("TAX_RATE", 0.033)
    ins_rate = cfg.get("INSURANCE_RATE", 0.097)

    start_date, end_date = _month_range(month)

    aggregates = (
        db.session.query(
            AttendanceRecord.employee_id,
            AttendanceRecord.emp_name,
            AttendanceRecord.dept,
            func.sum(AttendanceRecord.total_work_hours).label("total_hours"),
            func.sum(AttendanceRecord.overtime_hours).label("ot_hours"),
            func.sum(AttendanceRecord.night_hours).label("night_hours"),
            func.sum(AttendanceRecord.holiday_work_hours).label("holiday_hours"),
        )
        .filter(
            AttendanceRecord.work_date >= start_date,
            AttendanceRecord.work_date < end_date,
        )
        .group_by(
            AttendanceRecord.employee_id,
            AttendanceRecord.emp_name,
            AttendanceRecord.dept,
        )
        .all()
    )

    if not aggregates:
        return f"{month} 근태 기록이 없습니다."

    created = 0
    updated = 0
    for row in aggregates:
        employee_id, emp_name, dept = row.employee_id, row.emp_name, row.dept
        total_h = round(row.total_hours or 0, 2)
        ot_h = round(row.ot_hours or 0, 2)
        night_h = round(row.night_hours or 0, 2)
        holiday_h = round(row.holiday_hours or 0, 2)

        if salary_mode == "actual":
            base_salary = round(hourly * total_h)
        else:
            base_salary = hourly * std_monthly_hours

        ot_pay = round(ot_h * hourly * ot_mult)
        night_pay = round(night_h * hourly * night_prem)
        holiday_pay = round(holiday_h * hourly * ot_mult)

        gross = base_salary + ot_pay + night_pay + holiday_pay
        tax = round(gross * tax_rate)
        insurance = round(gross * ins_rate)

        adv_total = (
            db.session.query(func.coalesce(func.sum(AdvanceRequest.amount), 0))
            .filter(
                AdvanceRequest.employee_id == employee_id,
                AdvanceRequest.request_month == month,
                AdvanceRequest.status == "approved",
            )
            .scalar()
        )

        net = gross - tax - insurance - adv_total

        existing = Payslip.query.filter_by(employee_id=employee_id, month=month).first()
        if existing:
            existing.salary_mode = salary_mode
            existing.total_work_hours = total_h
            existing.ot_hours = ot_h
            existing.night_hours = night_h
            existing.holiday_hours = holiday_h
            existing.base_salary = base_salary
            existing.ot_pay = ot_pay
            existing.night_pay = night_pay
            existing.holiday_pay = holiday_pay
            existing.gross = gross
            existing.tax = tax
            existing.insurance = insurance
            existing.advance_deduction = adv_total
            existing.net = net
            updated += 1
        else:
            payslip = Payslip(
                employee_id=employee_id,
                emp_name=emp_name,
                dept=dept,
                month=month,
                salary_mode=salary_mode,
                total_work_hours=total_h,
                ot_hours=ot_h,
                night_hours=night_h,
                holiday_hours=holiday_h,
                base_salary=base_salary,
                ot_pay=ot_pay,
                night_pay=night_pay,
                holiday_pay=holiday_pay,
                gross=gross,
                tax=tax,
                insurance=insurance,
                advance_deduction=adv_total,
                net=net,
            )
            db.session.add(payslip)
            created += 1

    db.session.commit()
    return created, updated
