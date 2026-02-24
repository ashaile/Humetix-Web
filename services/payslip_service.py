"""급여 계산 비즈니스 로직 (payslip 라우트에서 추출)"""
from collections import defaultdict
from datetime import datetime, timedelta

from flask import current_app
from sqlalchemy import func

from config import Config
from models import AdvanceRequest, AttendanceRecord, Employee, OperationCalendarDay, Payslip, db
from services.wage_service import get_wage_config

ALLOWED_SALARY_MODES = {"standard", "actual", "daily_build"}

# 출근 인정 work_type (연차/반차 = 정상근무, 조퇴/지각 = 출근 인정)
ATTENDED_WORK_TYPES = {"normal", "night", "annual", "early"}


def _effective_salary_mode(wage_cfg, fallback_mode):
    """직원별 WageConfig의 calc_method를 반영한 실제 산정 방식을 결정한다.

    우선순위: 공수제(wage_type=daily) > calc_method > fallback_mode
    """
    if wage_cfg.get("wage_type") == "daily":
        return "daily"
    calc_method = wage_cfg.get("calc_method")
    if calc_method and calc_method in ("standard", "daily_build", "actual"):
        return calc_method
    return fallback_mode


def _calc_pay(wage_cfg, salary_mode, total_h, ot_h, night_h, holiday_h,
              attended_days=0, full_weeks=0):
    """WageConfig 딕셔너리 기반으로 급여를 계산한다.

    Args:
        wage_cfg: get_wage_config() 결과 딕셔너리
        salary_mode: 'standard' | 'actual' | 'daily_build' | 'daily'
        total_h, ot_h, night_h, holiday_h: 근무시간 합계
        attended_days: 출근일수 (daily_build용)
        full_weeks: 개근 주수 (daily_build용)

    Returns:
        (base_salary, weekly_holiday_pay, ot_pay, night_pay, holiday_pay)
    """
    wage_type = wage_cfg.get("wage_type", "hourly")
    hourly = wage_cfg.get("hourly_wage") or 10_320
    daily = wage_cfg.get("daily_wage") or 0
    std_hours = Config.MONTHLY_STANDARD_HOURS  # 월 소정근로시간 (주휴 포함, 기본 209)
    ot_mult = wage_cfg.get("overtime_rate") or 1.5
    night_prem = wage_cfg.get("night_bonus_rate") or 0.5
    ot_unit = wage_cfg.get("overtime_unit", "rate")
    ot_fixed = wage_cfg.get("overtime_fixed_amount") or 0
    std_work_hours = wage_cfg.get("standard_work_hours") or 8.0

    weekly_holiday_pay = 0

    if wage_type == "daily":
        # 공수제: 일당 기반
        work_days = total_h / std_work_hours if std_work_hours else 0
        base_salary = round(daily * work_days)

        if ot_unit == "fixed" and ot_fixed:
            ot_pay = round(ot_h * ot_fixed)
        else:
            hourly_equiv = daily / std_work_hours if std_work_hours else 0
            ot_pay = round(ot_h * hourly_equiv * ot_mult)

        night_pay = round(night_h * (daily / std_work_hours if std_work_hours else 0) * night_prem)
        holiday_pay = round(holiday_h * (daily / std_work_hours if std_work_hours else 0) * ot_mult)

    elif salary_mode == "daily_build":
        # 일급제 (0에서 쌓기): 출근일 × 일급 + 개근주 × 주휴
        daily_wage = hourly * std_work_hours
        base_salary = round(attended_days * daily_wage)
        weekly_holiday_pay = round(full_weeks * daily_wage)

        if ot_unit == "fixed" and ot_fixed:
            ot_pay = round(ot_h * ot_fixed)
        else:
            ot_pay = round(ot_h * hourly * ot_mult)

        night_pay = round(night_h * hourly * night_prem)
        holiday_pay = round(holiday_h * hourly * ot_mult)

    else:
        # 시급제 (standard 또는 actual)
        if salary_mode == "actual":
            base_salary = round(hourly * total_h)
        else:
            base_salary = hourly * std_hours

        if ot_unit == "fixed" and ot_fixed:
            ot_pay = round(ot_h * ot_fixed)
        else:
            ot_pay = round(ot_h * hourly * ot_mult)

        night_pay = round(night_h * hourly * night_prem)
        holiday_pay = round(holiday_h * hourly * ot_mult)

    return base_salary, weekly_holiday_pay, ot_pay, night_pay, holiday_pay


def _calc_attendance_info(employee_id, month, cfg):
    """출근/결근 정보를 종합적으로 계산한다.

    소정근로일: 월~금 중 공휴일 제외 (OperationCalendarDay 오버라이드 반영)
    출근 인정: normal, night, annual, early
    결근: absent, holiday 또는 기록 없음
    주휴 판정: 해당 주(월~일)의 소정근로일에 모두 출근해야 주휴 발생

    Returns:
        (absent_days, non_full_weeks, attended_days, full_weeks)
    """
    start_date, end_date = _month_range(month)

    # 캘린더 오버라이드 일괄 조회
    overrides = {
        row.work_date: row.day_type
        for row in OperationCalendarDay.query.filter(
            OperationCalendarDay.work_date >= start_date,
            OperationCalendarDay.work_date < end_date,
        ).all()
    }

    # 공휴일
    year = int(month.split("-")[0])
    holidays = set(cfg.get(f"PUBLIC_HOLIDAYS_{year}", []))

    def day_type(d):
        if d in overrides:
            return overrides[d]
        if d.weekday() == 6:        # 일요일 → 유급휴일
            return "paid_leave"
        if d.weekday() == 5:        # 토요일 → 무급휴일
            return "unpaid_leave"
        if d.strftime("%Y-%m-%d") in holidays:
            return "paid_leave"
        return "workday"

    # 소정근로일 집합 + 주별 그룹핑
    scheduled_workdays = set()
    weeks = defaultdict(set)         # (iso_year, iso_week) → set of workday dates

    d = start_date
    while d < end_date:
        if day_type(d) == "workday":
            scheduled_workdays.add(d)
            iso_year, iso_week, _ = d.isocalendar()
            weeks[(iso_year, iso_week)].add(d)
        d += timedelta(days=1)

    if not scheduled_workdays:
        return 0, 0, 0, 0

    # 직원 출근 기록 조회
    records = (
        AttendanceRecord.query
        .filter(
            AttendanceRecord.employee_id == employee_id,
            AttendanceRecord.work_date >= start_date,
            AttendanceRecord.work_date < end_date,
        )
        .all()
    )
    attended_dates = {r.work_date for r in records if r.work_type in ATTENDED_WORK_TYPES}

    # 결근일수 = 소정근로일 중 출근하지 않은 날
    absent_days = len(scheduled_workdays - attended_dates)
    attended_days = len(scheduled_workdays) - absent_days

    # 주 단위 개근 판정
    total_weeks = len(weeks)
    non_full_weeks = 0
    for week_key, week_scheduled in weeks.items():
        if not week_scheduled:
            continue
        if len(week_scheduled & attended_dates) < len(week_scheduled):
            non_full_weeks += 1
    full_weeks = total_weeks - non_full_weeks

    return absent_days, non_full_weeks, attended_days, full_weeks


def _calc_absence_deductions(wage_cfg, salary_mode, absent_days, non_full_weeks):
    """결근/주휴 공제 금액을 계산한다 (출석 카운트 기반).

    규칙:
    - standard(209h차감): 결근공제 + 주휴공제 적용
    - daily_build/actual/daily: 공제 불필요 (이미 반영됨)

    Returns:
        (absent_deduction, weekly_holiday_deduction)
    """
    # standard 모드만 결근/주휴 공제 적용
    if salary_mode != "standard":
        return 0, 0

    if absent_days == 0 and non_full_weeks == 0:
        return 0, 0

    hourly = wage_cfg.get("hourly_wage") or 10_320
    std_wh = wage_cfg.get("standard_work_hours") or 8.0

    absent_deduction = int(absent_days * hourly * std_wh)
    weekly_holiday_deduction = int(non_full_weeks * hourly * std_wh)

    return absent_deduction, weekly_holiday_deduction


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


def _calc_deductions(gross, emp_ins_type, cfg):
    """보험/세금 공제액 계산."""
    tax_rate = cfg.get("TAX_RATE", 0.033)
    pension_rate = cfg.get("PENSION_RATE", 0.0475)
    health_rate = cfg.get("HEALTH_RATE", 0.03595)
    longterm_rate = cfg.get("LONGTERM_CARE_RATE", 0.1314)
    employment_rate = cfg.get("EMPLOYMENT_RATE", 0.0115)

    if emp_ins_type == "4대보험":
        tax = 0
        pension = round(gross * pension_rate)
        health = round(gross * health_rate)
        longterm = round(health * longterm_rate)
        employment = round(gross * employment_rate)
    else:
        tax = round(gross * tax_rate)
        pension = 0
        health = 0
        longterm = 0
        employment = 0

    insurance = pension + health + longterm + employment
    return tax, pension, health, longterm, employment, insurance


def compute_payslips(month: str, salary_mode: str):
    """월별 급여를 계산하고 DB에 저장한다.

    Returns (created, updated, skipped) 또는 error 문자열.
    """
    cfg = current_app.config

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
    skipped = 0
    for row in aggregates:
        employee_id, emp_name, dept = row.employee_id, row.emp_name, row.dept
        total_h = round(row.total_hours or 0, 2)
        ot_h = round(row.ot_hours or 0, 2)
        night_h = round(row.night_hours or 0, 2)
        holiday_h = round(row.holiday_hours or 0, 2)

        # 직원별 WageConfig 해석 (직원 > 현장 > 시스템 기본값)
        wage_cfg = get_wage_config(employee_id=employee_id)
        effective_mode = _effective_salary_mode(wage_cfg, salary_mode)

        # 출근/결근 정보
        absent_days, non_full_weeks, attended_days, full_weeks = (
            _calc_attendance_info(employee_id, month, cfg)
        )

        # 급여 계산
        base_salary, weekly_hol_pay, ot_pay, night_pay, holiday_pay = _calc_pay(
            wage_cfg, effective_mode, total_h, ot_h, night_h, holiday_h,
            attended_days, full_weeks,
        )

        # 결근/주휴 공제 (standard만 해당)
        absent_ded, weekly_hol_ded = _calc_absence_deductions(
            wage_cfg, effective_mode, absent_days, non_full_weeks
        )

        gross = max(0, base_salary + weekly_hol_pay + ot_pay + night_pay + holiday_pay
                     - absent_ded - weekly_hol_ded)

        # 직원별 보험 유형 조회
        emp = db.session.get(Employee, employee_id)
        emp_ins_type = emp.insurance_type if emp else "3.3%"
        tax, pension, health, longterm, employment, insurance = _calc_deductions(gross, emp_ins_type, cfg)

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
            if existing.is_manual:
                skipped += 1
                continue
            existing.salary_mode = effective_mode
            existing.total_work_hours = total_h
            existing.ot_hours = ot_h
            existing.night_hours = night_h
            existing.holiday_hours = holiday_h
            existing.base_salary = base_salary
            existing.weekly_holiday_pay = weekly_hol_pay
            existing.ot_pay = ot_pay
            existing.night_pay = night_pay
            existing.holiday_pay = holiday_pay
            existing.absent_days = absent_days
            existing.absent_deduction = absent_ded
            existing.weekly_holiday_deduction = weekly_hol_ded
            existing.gross = gross
            existing.tax = tax
            existing.pension = pension
            existing.health_ins = health
            existing.longterm_care = longterm
            existing.employment_ins = employment
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
                salary_mode=effective_mode,
                total_work_hours=total_h,
                ot_hours=ot_h,
                night_hours=night_h,
                holiday_hours=holiday_h,
                base_salary=base_salary,
                weekly_holiday_pay=weekly_hol_pay,
                ot_pay=ot_pay,
                night_pay=night_pay,
                holiday_pay=holiday_pay,
                absent_days=absent_days,
                absent_deduction=absent_ded,
                weekly_holiday_deduction=weekly_hol_ded,
                gross=gross,
                tax=tax,
                pension=pension,
                health_ins=health,
                longterm_care=longterm,
                employment_ins=employment,
                insurance=insurance,
                advance_deduction=adv_total,
                net=net,
            )
            db.session.add(payslip)
            created += 1

    db.session.commit()
    return created, updated, skipped


def compute_single_payslip(employee_id: int, month: str, salary_mode: str):
    """특정 직원 1명의 급여를 계산하고 DB에 저장한다.

    Returns dict with result info, or error string.
    """
    emp = db.session.get(Employee, employee_id)
    if not emp:
        return "직원을 찾을 수 없습니다."

    cfg = current_app.config

    start_date, end_date = _month_range(month)

    row = (
        db.session.query(
            AttendanceRecord.emp_name,
            AttendanceRecord.dept,
            func.sum(AttendanceRecord.total_work_hours).label("total_hours"),
            func.sum(AttendanceRecord.overtime_hours).label("ot_hours"),
            func.sum(AttendanceRecord.night_hours).label("night_hours"),
            func.sum(AttendanceRecord.holiday_work_hours).label("holiday_hours"),
        )
        .filter(
            AttendanceRecord.employee_id == employee_id,
            AttendanceRecord.work_date >= start_date,
            AttendanceRecord.work_date < end_date,
        )
        .group_by(AttendanceRecord.emp_name, AttendanceRecord.dept)
        .first()
    )

    if not row or not row.total_hours:
        return f"{emp.name}의 {month} 근태 기록이 없습니다."

    emp_name = row.emp_name
    dept = row.dept
    total_h = round(row.total_hours or 0, 2)
    ot_h = round(row.ot_hours or 0, 2)
    night_h = round(row.night_hours or 0, 2)
    holiday_h = round(row.holiday_hours or 0, 2)

    # 직원별 WageConfig 해석 (직원 > 현장 > 시스템 기본값)
    wage_cfg = get_wage_config(employee_id=employee_id)
    effective_mode = _effective_salary_mode(wage_cfg, salary_mode)

    # 출근/결근 정보
    absent_days, non_full_weeks, attended_days, full_weeks = (
        _calc_attendance_info(employee_id, month, cfg)
    )

    # 급여 계산
    base_salary, weekly_hol_pay, ot_pay, night_pay, holiday_pay = _calc_pay(
        wage_cfg, effective_mode, total_h, ot_h, night_h, holiday_h,
        attended_days, full_weeks,
    )

    # 결근/주휴 공제 (standard만 해당)
    absent_ded, weekly_hol_ded = _calc_absence_deductions(
        wage_cfg, effective_mode, absent_days, non_full_weeks
    )

    gross = max(0, base_salary + weekly_hol_pay + ot_pay + night_pay + holiday_pay
                 - absent_ded - weekly_hol_ded)

    emp_ins_type = emp.insurance_type if emp else "3.3%"
    tax, pension, health, longterm, employment, insurance = _calc_deductions(gross, emp_ins_type, cfg)

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
    action = "updated"
    if existing:
        if existing.is_manual:
            return "수동 수정된 명세서입니다. 초기화 후 재생성하세요."
        existing.salary_mode = effective_mode
        existing.total_work_hours = total_h
        existing.ot_hours = ot_h
        existing.night_hours = night_h
        existing.holiday_hours = holiday_h
        existing.base_salary = base_salary
        existing.weekly_holiday_pay = weekly_hol_pay
        existing.ot_pay = ot_pay
        existing.night_pay = night_pay
        existing.holiday_pay = holiday_pay
        existing.absent_days = absent_days
        existing.absent_deduction = absent_ded
        existing.weekly_holiday_deduction = weekly_hol_ded
        existing.gross = gross
        existing.tax = tax
        existing.pension = pension
        existing.health_ins = health
        existing.longterm_care = longterm
        existing.employment_ins = employment
        existing.insurance = insurance
        existing.advance_deduction = adv_total
        existing.net = net
    else:
        action = "created"
        payslip = Payslip(
            employee_id=employee_id,
            emp_name=emp_name,
            dept=dept,
            month=month,
            salary_mode=effective_mode,
            total_work_hours=total_h,
            ot_hours=ot_h,
            night_hours=night_h,
            holiday_hours=holiday_h,
            base_salary=base_salary,
            weekly_holiday_pay=weekly_hol_pay,
            ot_pay=ot_pay,
            night_pay=night_pay,
            holiday_pay=holiday_pay,
            absent_days=absent_days,
            absent_deduction=absent_ded,
            weekly_holiday_deduction=weekly_hol_ded,
            gross=gross,
            tax=tax,
            pension=pension,
            health_ins=health,
            longterm_care=longterm,
            employment_ins=employment,
            insurance=insurance,
            advance_deduction=adv_total,
            net=net,
        )
        db.session.add(payslip)

    db.session.commit()
    return {"action": action, "emp_name": emp_name}
