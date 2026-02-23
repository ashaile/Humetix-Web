"""calc_work_hours 급여 계산 핵심 로직 엣지 케이스 테스트"""
from datetime import date
import pytest
from routes.attendance import calc_work_hours

CFG = {
    "BREAK_HOURS": 1.0,
    "STANDARD_WORK_HOURS": 8.0,
    "NIGHT_START": 22,
    "NIGHT_END": 6,
    "PUBLIC_HOLIDAYS_2026": ["2026-01-01", "2026-03-01"],
}


# ── 기본 근무시간 계산 ──────────────────────────────────

def test_normal_8h_no_overtime():
    """09:00~18:00 (1h 휴식) → 8h, OT 0"""
    total, ot, night, holiday = calc_work_hours("09:00", "18:00", CFG)
    assert total == 8.0
    assert ot == 0.0
    assert night == 0.0
    assert holiday == 0.0


def test_overtime_11h():
    """09:00~21:00 (1h 휴식) → 11h 근무, OT 3h"""
    total, ot, night, holiday = calc_work_hours("09:00", "21:00", CFG)
    assert total == 11.0
    assert ot == 3.0
    assert holiday == 0.0


def test_short_shift_under_break_time():
    """30분 근무 (휴식 60분 > 근무) → 0h"""
    total, ot, night, holiday = calc_work_hours("09:00", "09:30", CFG)
    assert total == 0.0
    assert ot == 0.0


# ── 야간 수당 계산 ──────────────────────────────────────

def test_night_work_after_22():
    """22:00~23:00 → 야간 1h (휴식 없음, 단시간 근무로 break 차감 없음)"""
    total, ot, night, holiday = calc_work_hours("22:00", "23:00", CFG)
    # 1h 근무 - 1h 휴식 = 0h total, 야간도 0
    assert total == 0.0


def test_night_work_long_shift():
    """14:00~23:00 → 8h 근무, 야간 1h (주간 휴게 12:30~13:30, 야간 구간 차감 없음)"""
    total, ot, night, holiday = calc_work_hours("14:00", "23:00", CFG)
    assert total == 8.0
    assert night == 1.0   # 22:00~23:00 = 1h, 주간 근무라 야간 차감 없음
    assert ot == 0.0


def test_midnight_crossing_shift():
    """22:00~06:00 자정 넘김 → 7h 근무, 야간 7h (야간 휴게 00:00~01:00 차감)"""
    total, ot, night, holiday = calc_work_hours("22:00", "06:00", CFG)
    assert total == 7.0
    assert night == 7.0   # 22:00~06:00=8h, 야간 휴게 1h 차감 → 7h


def test_late_night_full_shift():
    """20:00~05:00 → 8h 근무, 야간 6h (15시 이후 시작 = 야간 근무, 휴게 00:00~01:00 차감)"""
    total, ot, night, holiday = calc_work_hours("20:00", "05:00", CFG)
    assert total == 8.0
    assert night == 6.0   # 22:00~05:00=7h, 야간 휴게 1h 차감 → 6h


# ── 휴일/공휴일 근무 ────────────────────────────────────

def test_weekend_work_saturday():
    """토요일 근무 → holiday_work_hours에 집계, OT 없음"""
    saturday = date(2026, 2, 21)  # 토요일
    assert saturday.weekday() == 5
    total, ot, night, holiday = calc_work_hours("09:00", "18:00", CFG, work_date=saturday)
    assert total == 8.0
    assert ot == 0.0
    assert holiday == 8.0


def test_weekend_work_sunday():
    """일요일 근무 → holiday_work_hours"""
    sunday = date(2026, 2, 22)  # 일요일
    assert sunday.weekday() == 6
    total, ot, night, holiday = calc_work_hours("09:00", "18:00", CFG, work_date=sunday)
    assert holiday == 8.0


def test_public_holiday_work():
    """공휴일(삼일절) 근무 → holiday_work_hours"""
    holiday_date = date(2026, 3, 1)
    total, ot, night, holiday = calc_work_hours("09:00", "18:00", CFG, work_date=holiday_date)
    assert total == 8.0
    assert holiday == 8.0
    assert ot == 0.0


def test_new_years_day_holiday():
    """신정(1월 1일) 근무 → holiday_work_hours"""
    new_year = date(2026, 1, 1)
    total, ot, night, holiday = calc_work_hours("09:00", "18:00", CFG, work_date=new_year)
    assert holiday == 8.0


def test_weekday_is_not_holiday():
    """평일 근무는 holiday 아님"""
    weekday = date(2026, 2, 23)  # 월요일
    assert weekday.weekday() == 0
    total, ot, night, holiday = calc_work_hours("09:00", "18:00", CFG, work_date=weekday)
    assert holiday == 0.0
    assert total == 8.0


# ── calendar_day_type 오버라이드 ────────────────────────

def test_calendar_override_workday_on_holiday():
    """공휴일이지만 캘린더에서 workday로 설정 → 일반 근무 처리"""
    holiday_date = date(2026, 3, 1)
    total, ot, night, holiday = calc_work_hours(
        "09:00", "20:00", CFG, work_date=holiday_date, calendar_day_type="workday"
    )
    assert ot == 2.0
    assert holiday == 0.0


def test_calendar_day_type_holiday_not_recognized():
    """'holiday'는 CALENDAR_DAY_TYPES에 없어 오버라이드 무효 → 평일 일반 근무 처리"""
    weekday = date(2026, 2, 23)  # 월요일
    total, ot, night, holiday = calc_work_hours(
        "09:00", "18:00", CFG, work_date=weekday, calendar_day_type="holiday"
    )
    # "holiday"는 캘린더 타입으로 인식 안 됨 → 평일로 처리
    assert total == 8.0
    assert holiday == 0.0
    assert ot == 0.0
