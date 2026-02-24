"""연차/퇴직금 계산 서비스 — FIFO 발생/사용 추적 포함."""

import calendar as _cal
import logging
from datetime import date

from dateutil.relativedelta import relativedelta
from sqlalchemy import extract, func
from sqlalchemy.orm import joinedload

from config import Config
from models import AttendanceRecord, Employee, LeaveAccrual, LeaveBalance, LeaveUsage, OperationCalendarDay, Payslip, db

logger = logging.getLogger(__name__)


# ────────────────────────────────────────────
# 기존: 연차 계산
# ────────────────────────────────────────────

def calc_annual_leave(hire_date, reference_date=None):
    """근로기준법 제60조에 따라 연차유급휴가 일수를 계산한다.

    - 1년 미만: 1개월 개근 시 1일 (최대 11일)
    - 1년 이상: 15일 + 2년마다 1일 가산 (최대 25일)

    Returns:
        float: 발생 연차 일수
    """
    if not hire_date:
        return 0

    ref = reference_date or date.today()
    if hire_date > ref:
        return 0

    delta = relativedelta(ref, hire_date)
    total_years = delta.years
    total_months = delta.years * 12 + delta.months

    if total_years < 1:
        return min(total_months, 11)

    extra = (total_years - 1) // 2
    return min(15 + extra, 25)



# ────────────────────────────────────────────
# 발생(Accrual) 관리
# ────────────────────────────────────────────

def generate_accruals(employee_id, year):
    """입사일 기반으로 해당 연도의 발생 레코드를 자동 생성한다.

    - 1년 미만: month=1~12 각 1일 (입사 이후 월만)
    - 1년 이상: month=0에 일괄 발생 (15일+가산)
    - 이미 존재하는 month는 건너뜀

    Returns:
        int: 새로 생성된 accrual 수
    """
    emp = db.session.get(Employee, employee_id)
    if not emp or not emp.hire_date:
        return 0

    ref_date = date(year, 12, 31)
    delta = relativedelta(ref_date, emp.hire_date)
    total_years = delta.years

    existing_months = set(
        r[0] for r in db.session.query(LeaveAccrual.month)
        .filter_by(employee_id=employee_id, year=year)
        .all()
    )

    created = 0

    if total_years >= 1:
        # 1년 이상: 연초 일괄 발생
        if 0 not in existing_months:
            entitled = calc_annual_leave(emp.hire_date, ref_date)

            # 1년 전환 시 이미 사용한 월차 공제 (근로기준법 제60조 제3항)
            # 입사 1년차에 사용한 월차 일수를 15일에서 차감
            if total_years == 1:
                prev_year = year - 1
                used_monthly = (
                    db.session.query(func.count(LeaveAccrual.id))
                    .filter_by(employee_id=employee_id, year=prev_year)
                    .filter(LeaveAccrual.month > 0)  # month=0 제외 (일괄발생)
                    .scalar()
                ) or 0
                if used_monthly > 0:
                    entitled = max(entitled - used_monthly, 0)

            accrual = LeaveAccrual(
                employee_id=employee_id,
                year=year,
                month=0,
                accrual_type="annual_bulk",
                days=entitled,
                remaining=entitled,
                description=f"연차 {entitled}일 (근로기준법 제60조)",
            )
            db.session.add(accrual)
            created += 1
    else:
        # 1년 미만: 입사 이후 월별 만근 월차
        hire_ym = emp.hire_date.year * 12 + emp.hire_date.month
        for m in range(1, 13):
            if m in existing_months:
                continue
            target_ym = year * 12 + m
            # 입사월 이후만 (입사 당월 제외, 그 다음 달부터)
            if target_ym <= hire_ym:
                continue
            # 최대 11일 제한 확인
            months_since_hire = target_ym - hire_ym
            if months_since_hire > 11:
                continue
            accrual = LeaveAccrual(
                employee_id=employee_id,
                year=year,
                month=m,
                accrual_type="monthly",
                days=1,
                remaining=1,
                description=f"{m}월 만근 월차",
            )
            db.session.add(accrual)
            created += 1

    if created:
        db.session.flush()
    return created


# ────────────────────────────────────────────
# 사용(Usage) 관리 — FIFO
# ────────────────────────────────────────────

def register_usage_fifo(employee_id, use_date, days=1.0, description=""):
    """연차 사용을 FIFO로 등록한다.

    가장 오래된(year ASC, month ASC) 발생분의 remaining부터 차감.
    1건의 사용이 여러 accrual에 걸칠 수 있음.

    Returns:
        list[LeaveUsage]: 생성된 사용 레코드 목록
    """
    accruals = (
        LeaveAccrual.query
        .filter_by(employee_id=employee_id)
        .filter(LeaveAccrual.remaining > 0)
        .order_by(LeaveAccrual.year.asc(), LeaveAccrual.month.asc())
        .all()
    )

    remaining_to_use = days
    created_usages = []

    for accrual in accruals:
        if remaining_to_use <= 0:
            break
        consume = min(accrual.remaining, remaining_to_use)
        accrual.remaining = round(accrual.remaining - consume, 2)
        remaining_to_use = round(remaining_to_use - consume, 2)

        usage = LeaveUsage(
            employee_id=employee_id,
            accrual_id=accrual.id,
            use_date=use_date,
            days=consume,
            description=description,
        )
        db.session.add(usage)
        created_usages.append(usage)

    # 잔여 부족 시 초과사용 (accrual_id=NULL)
    if remaining_to_use > 0:
        usage = LeaveUsage(
            employee_id=employee_id,
            accrual_id=None,
            use_date=use_date,
            days=remaining_to_use,
            description=(description + " (초과사용)").strip(),
        )
        db.session.add(usage)
        created_usages.append(usage)

    db.session.flush()

    # LeaveBalance 캐시 갱신
    sync_single_balance(employee_id, use_date.year)

    return created_usages


def delete_usage(usage_id):
    """사용 기록 삭제 + 발생분 잔여 복원.

    Returns:
        dict: 결과 메시지
    """
    usage = db.session.get(LeaveUsage, usage_id)
    if not usage:
        return {"error": "사용 기록을 찾을 수 없습니다."}

    emp_id = usage.employee_id
    year = usage.use_date.year if usage.use_date else date.today().year

    # accrual remaining 복원
    if usage.accrual_id and usage.accrual:
        usage.accrual.remaining = round(usage.accrual.remaining + usage.days, 2)

    db.session.delete(usage)
    db.session.flush()
    sync_single_balance(emp_id, year)

    return {"success": True, "message": "사용 기록이 삭제되었습니다."}


def delete_accrual(accrual_id):
    """발생 기록 삭제 — 연결된 사용 기록도 함께 삭제.

    Returns:
        dict: 결과 메시지
    """
    accrual = db.session.get(LeaveAccrual, accrual_id)
    if not accrual:
        return {"error": "발생 기록을 찾을 수 없습니다."}

    emp_id = accrual.employee_id
    year = accrual.year

    # 연결된 usage가 있으면 accrual_id를 NULL로 (orphan 처리)
    for usage in accrual.usage_links:
        usage.accrual_id = None

    db.session.delete(accrual)
    db.session.flush()
    sync_single_balance(emp_id, year)

    return {"success": True, "message": "발생 기록이 삭제되었습니다."}


# ────────────────────────────────────────────
# 만근 판단 + 자동 발생
# ────────────────────────────────────────────

def get_working_days(year, month):
    """해당 월의 소정근로일수(주말·공휴일 제외 평일)를 반환한다.

    판단 우선순위:
    1) OperationCalendarDay 테이블에 해당 월 데이터가 있으면 day_type='workday' 수
    2) 없으면 config 공휴일 + 주말 제외 평일 수
    """
    last_day = _cal.monthrange(year, month)[1]
    start = date(year, month, 1)
    end = date(year, month, last_day)

    # OperationCalendarDay 오버라이드 확인
    overrides = {
        d.work_date: d.day_type
        for d in OperationCalendarDay.query.filter(
            OperationCalendarDay.work_date >= start,
            OperationCalendarDay.work_date <= end,
        ).all()
    }

    holidays_set = set(Config.get_public_holidays(year))
    working = 0
    for day_num in range(1, last_day + 1):
        d = date(year, month, day_num)
        if d in overrides:
            if overrides[d] == "workday":
                working += 1
        else:
            # 기본: 토(5)/일(6) + 공휴일 제외
            if d.weekday() < 5 and d.strftime("%Y-%m-%d") not in holidays_set:
                working += 1
    return working


def check_full_attendance(employee_id, year, month):
    """해당 월 만근 여부를 판단한다.

    출근 인정: work_type in ('normal', 'night', 'annual')
    만근 = 출근일수 >= 소정근로일수

    Returns:
        (is_full, worked_days, required_days)
    """
    required = get_working_days(year, month)
    if required == 0:
        return False, 0, 0

    last_day = _cal.monthrange(year, month)[1]
    start = date(year, month, 1)
    end = date(year, month, last_day)

    worked = (
        db.session.query(func.count(AttendanceRecord.id))
        .filter(
            AttendanceRecord.employee_id == employee_id,
            AttendanceRecord.work_date >= start,
            AttendanceRecord.work_date <= end,
            AttendanceRecord.work_type.in_(("normal", "night", "annual")),
        )
        .scalar()
    ) or 0

    return worked >= required, worked, required


def _auto_generate_accruals(employee_id, year):
    """근태 데이터 기반 만근 자동 발생. 이미 accrual 있는 월은 스킵.

    Returns:
        int: 새로 생성된 accrual 수
    """
    today = date.today()

    # 해당 직원의 해당 연도 근태 데이터가 있는 월 목록
    attendance_months = (
        db.session.query(
            func.distinct(extract("month", AttendanceRecord.work_date))
        )
        .filter(
            AttendanceRecord.employee_id == employee_id,
            extract("year", AttendanceRecord.work_date) == year,
        )
        .all()
    )
    months_with_data = {int(m[0]) for m in attendance_months if m[0]}

    if not months_with_data:
        return 0

    # 이미 존재하는 accrual month
    existing_months = set(
        r[0] for r in db.session.query(LeaveAccrual.month)
        .filter_by(employee_id=employee_id, year=year)
        .all()
    )

    created = 0
    for month in sorted(months_with_data):
        # 진행 중인 월은 스킵
        if year == today.year and month >= today.month:
            continue
        # 이미 accrual 있으면 스킵 (수동 등록 보호)
        if month in existing_months:
            continue

        is_full, worked, required = check_full_attendance(employee_id, year, month)
        if not is_full:
            continue

        accrual = LeaveAccrual(
            employee_id=employee_id,
            year=year,
            month=month,
            accrual_type="auto_monthly",
            days=1,
            remaining=1,
            description=f"{month}월 만근 ({worked}/{required}일)",
        )
        db.session.add(accrual)
        created += 1

    if created:
        db.session.flush()
    return created


# ────────────────────────────────────────────
# 캐시 동기화
# ────────────────────────────────────────────

def sync_single_balance(employee_id, year):
    """단일 직원의 LeaveBalance를 Accrual/Usage 합계로 재계산. 이월 포함."""
    # 1) 당해 연도 발생 합계
    total_accrued = (
        db.session.query(func.coalesce(func.sum(LeaveAccrual.days), 0))
        .filter_by(employee_id=employee_id, year=year)
        .scalar()
    ) or 0

    # 2) 당해 연도 사용 합계
    total_used = (
        db.session.query(func.coalesce(func.sum(LeaveUsage.days), 0))
        .filter(
            LeaveUsage.employee_id == employee_id,
            extract("year", LeaveUsage.use_date) == year,
        )
        .scalar()
    ) or 0

    # 3) 이월분: 직전 연도 accrual 중 remaining > 0 합계 (연차는 1년 후 소멸)
    carryover = (
        db.session.query(func.coalesce(func.sum(LeaveAccrual.remaining), 0))
        .filter(
            LeaveAccrual.employee_id == employee_id,
            LeaveAccrual.year == year - 1,
            LeaveAccrual.remaining > 0,
        )
        .scalar()
    ) or 0

    # 4) 잔여 = 당해 발생 + 이월 - 당해 사용
    remaining = max(total_accrued + carryover - total_used, 0)

    balance = LeaveBalance.query.filter_by(
        employee_id=employee_id, year=year
    ).first()

    if balance:
        balance.entitled = total_accrued
        balance.used = total_used
        balance.remaining = remaining
        balance.carryover = carryover
    else:
        balance = LeaveBalance(
            employee_id=employee_id,
            year=year,
            entitled=total_accrued,
            used=total_used,
            remaining=remaining,
            carryover=carryover,
        )
        db.session.add(balance)


def sync_employees_to_leave(year=None):
    """활성 직원 전원을 연차관리에 등록 (LeaveBalance 미존재 시 생성)."""
    target_year = year or date.today().year
    employees = Employee.query.filter_by(is_active=True).all()

    existing_ids = set(
        r[0] for r in db.session.query(LeaveBalance.employee_id)
        .filter_by(year=target_year)
        .all()
    )

    added = 0
    for emp in employees:
        if emp.id in existing_ids:
            continue
        balance = LeaveBalance(
            employee_id=emp.id,
            year=target_year,
            entitled=0,
            used=0,
            remaining=0,
            carryover=0,
        )
        db.session.add(balance)
        added += 1

    if added:
        db.session.flush()
    logger.info("직원 동기화: %d명 신규 등록, %d명 기존", added, len(existing_ids))
    return added, len(existing_ids)


def sync_leave_balances(year=None, include_attendance=True):
    """전 직원 연차를 일괄 동기화한다.

    Args:
        year: 대상 연도
        include_attendance: True면 근태 엑셀 데이터 기반 동기화 포함
                           (만근 자동발생 + 사용 가져오기)

    Returns:
        (synced, skipped, auto_created): 동기화/스킵/자동발생 수
    """
    target_year = year or date.today().year

    employees = Employee.query.filter_by(is_active=True).all()
    synced = 0
    skipped = 0
    total_auto = 0

    for emp in employees:
        if include_attendance:
            # (1) 만근 월 자동 연차 발생
            total_auto += _auto_generate_accruals(emp.id, target_year)

            # (2) AttendanceRecord(work_type='annual')를 LeaveUsage로 변환
            _import_attendance_usages(emp.id, target_year)

        # (3) Balance 캐시 갱신
        sync_single_balance(emp.id, target_year)
        synced += 1

    db.session.flush()
    logger.info("연차 동기화 완료: %d명 처리, 자동발생 %d건, 근태포함=%s",
                synced, total_auto, include_attendance)
    return synced, skipped, total_auto


def _import_attendance_usages(employee_id, year):
    """AttendanceRecord(work_type='annual')를 LeaveUsage로 변환 (중복 방지)."""
    start = date(year, 1, 1)
    end = date(year, 12, 31)

    records = (
        AttendanceRecord.query
        .filter(
            AttendanceRecord.employee_id == employee_id,
            AttendanceRecord.work_type == "annual",
            AttendanceRecord.work_date >= start,
            AttendanceRecord.work_date <= end,
        )
        .all()
    )

    # 이미 존재하는 usage의 use_date 셋
    existing_dates = set(
        r[0] for r in db.session.query(LeaveUsage.use_date)
        .filter_by(employee_id=employee_id)
        .filter(LeaveUsage.use_date >= start, LeaveUsage.use_date <= end)
        .all()
    )

    # FIFO 대상 accrual을 한 번만 조회 (루프 내 반복 쿼리 제거)
    accruals = (
        LeaveAccrual.query
        .filter_by(employee_id=employee_id)
        .filter(LeaveAccrual.remaining > 0)
        .order_by(LeaveAccrual.year.asc(), LeaveAccrual.month.asc())
        .all()
    )

    for rec in records:
        if rec.work_date in existing_dates:
            continue
        # FIFO 차감 — 0.5일 단위도 처리
        remaining_to_use = 1.0
        for a in accruals:
            if remaining_to_use <= 0:
                break
            if a.remaining <= 0:
                continue
            consume = min(a.remaining, remaining_to_use)
            a.remaining = round(a.remaining - consume, 2)
            remaining_to_use = round(remaining_to_use - consume, 2)

            usage = LeaveUsage(
                employee_id=employee_id,
                accrual_id=a.id,
                use_date=rec.work_date,
                days=consume,
                description="근태기록 연동",
            )
            db.session.add(usage)

        # 잔여 부족 시 초과사용
        if remaining_to_use > 0:
            usage = LeaveUsage(
                employee_id=employee_id,
                accrual_id=None,
                use_date=rec.work_date,
                days=remaining_to_use,
                description="근태기록 연동 (초과사용)",
            )
            db.session.add(usage)


def get_employee_leave_detail(employee_id, year):
    """직원별 연차 상세 데이터를 조합하여 반환한다. 이월 포함.

    Returns:
        dict: employee, year, accruals, usages, summary, monthly_grid,
              carryover_accruals, carryover_total
    """
    emp = db.session.get(Employee, employee_id)
    if not emp:
        return None

    accruals = (
        LeaveAccrual.query
        .filter_by(employee_id=employee_id, year=year)
        .order_by(LeaveAccrual.month.asc())
        .all()
    )

    usages = (
        LeaveUsage.query
        .filter_by(employee_id=employee_id)
        .filter(
            extract("year", LeaveUsage.use_date) == year,
        )
        .options(joinedload(LeaveUsage.accrual))
        .order_by(LeaveUsage.use_date.asc())
        .all()
    )

    # 이월분: 직전 연도 accrual 중 remaining > 0 (연차는 1년 후 소멸)
    carryover_accruals = (
        LeaveAccrual.query
        .filter(
            LeaveAccrual.employee_id == employee_id,
            LeaveAccrual.year == year - 1,
            LeaveAccrual.remaining > 0,
        )
        .order_by(LeaveAccrual.year.asc(), LeaveAccrual.month.asc())
        .all()
    )
    carryover_total = sum(a.remaining for a in carryover_accruals)

    total_accrued = sum(a.days for a in accruals)
    total_used = sum(u.days for u in usages)
    total_remaining = max(total_accrued + carryover_total - total_used, 0)
    total_pool = total_accrued + carryover_total

    # 12개월 미니 그리드 데이터
    monthly_grid = {}
    for m in range(1, 13):
        monthly_grid[m] = {"accrued": False, "days": 0, "remaining": 0}
    for a in accruals:
        if 1 <= a.month <= 12:
            monthly_grid[a.month] = {
                "accrued": True,
                "days": a.days,
                "remaining": a.remaining,
                "id": a.id,
            }

    # 일괄 발생(month=0) 정보
    bulk_accrual = next((a for a in accruals if a.month == 0), None)

    # 근속 계산
    tenure_str = ""
    if emp.hire_date:
        delta = relativedelta(date.today(), emp.hire_date)
        parts = []
        if delta.years:
            parts.append(f"{delta.years}년")
        if delta.months:
            parts.append(f"{delta.months}개월")
        if not parts:
            parts.append(f"{delta.days}일")
        tenure_str = " ".join(parts)

    return {
        "employee": emp,
        "year": year,
        "accruals": accruals,
        "usages": usages,
        "bulk_accrual": bulk_accrual,
        "carryover_accruals": carryover_accruals,
        "carryover_total": carryover_total,
        "summary": {
            "entitled": total_accrued,
            "carryover": carryover_total,
            "used": total_used,
            "remaining": total_remaining,
            "pct": round(total_used / total_pool * 100) if total_pool > 0 else 0,
        },
        "monthly_grid": monthly_grid,
        "tenure": tenure_str,
    }


# ────────────────────────────────────────────
# 퇴직금 (기존 유지)
# ────────────────────────────────────────────

def calc_severance(employee_id):
    """퇴직급여법에 따라 퇴직금을 계산한다.

    - 1년 이상 근속 대상
    - 평균임금 = 최근 3개월 Payslip.gross 합 / 90일
    - 퇴직금 = 평균일급 x 30 x (근속일수 / 365)

    Returns:
        dict: 계산 결과 또는 에러 메시지
    """
    emp = db.session.get(Employee, employee_id)
    if not emp:
        return {"error": "직원을 찾을 수 없습니다."}

    if not emp.hire_date:
        return {"error": "입사일이 등록되지 않았습니다."}

    end_date = emp.resign_date or date.today()
    service_days = (end_date - emp.hire_date).days

    if service_days < 365:
        return {
            "employee_name": emp.name,
            "hire_date": emp.hire_date.strftime("%Y-%m-%d"),
            "service_days": service_days,
            "eligible": False,
            "message": "근속 1년 미만으로 퇴직금 대상이 아닙니다.",
            "severance": 0,
        }

    recent_payslips = (
        Payslip.query
        .filter_by(employee_id=employee_id)
        .order_by(Payslip.month.desc())
        .limit(3)
        .all()
    )

    if not recent_payslips:
        return {
            "employee_name": emp.name,
            "hire_date": emp.hire_date.strftime("%Y-%m-%d"),
            "service_days": service_days,
            "eligible": True,
            "message": "급여 데이터가 없어 퇴직금을 계산할 수 없습니다.",
            "severance": 0,
        }

    total_gross = sum(p.gross for p in recent_payslips)
    months_count = len(recent_payslips)
    if months_count < 3:
        return {
            "employee_name": emp.name,
            "hire_date": emp.hire_date.strftime("%Y-%m-%d"),
            "service_days": service_days,
            "eligible": True,
            "message": f"급여 데이터가 {months_count}건뿐입니다. 최소 3개월 데이터가 필요합니다.",
            "severance": 0,
        }
    avg_daily = total_gross / 90  # 직전 3개월 = 90일 기준
    severance = round(avg_daily * 30 * (service_days / 365))

    return {
        "employee_name": emp.name,
        "hire_date": emp.hire_date.strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d"),
        "service_days": service_days,
        "service_years": round(service_days / 365, 1),
        "eligible": True,
        "recent_months": months_count,
        "total_gross_3m": total_gross,
        "avg_daily_wage": round(avg_daily),
        "severance": severance,
    }
