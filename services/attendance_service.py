"""근태 관련 비즈니스 로직 (근무시간 계산, 날짜 유형 판별 등)"""
import re
from datetime import datetime

from flask import current_app

from models import OperationCalendarDay

ALLOWED_WORK_TYPES = {"normal", "night", "annual", "absent", "holiday", "early"}
TIME_REQUIRED_TYPES = {"normal", "night"}
CALENDAR_DAY_TYPES = {"workday", "paid_leave", "unpaid_leave"}
LEAVE_DAY_TYPES = {"paid_leave", "unpaid_leave"}


def _parse_date(value: str):
    return datetime.strptime(value, "%Y-%m-%d").date()


def _validate_hhmm(value: str) -> bool:
    if not value or not re.fullmatch(r"\d{2}:\d{2}", value):
        return False
    hh, mm = value.split(":")
    return 0 <= int(hh) <= 23 and 0 <= int(mm) <= 59


def _time_to_minutes(hhmm: str) -> int:
    h, m = map(int, hhmm.split(":"))
    return h * 60 + m


def _minutes_in_range(start_min, end_min, range_start_min, range_end_min):
    if range_start_min >= range_end_min:
        part1 = _minutes_in_range(start_min, end_min, range_start_min, 24 * 60)
        part2 = _minutes_in_range(start_min, end_min, 0, range_end_min)
        return part1 + part2

    overlap_start = max(start_min, range_start_min)
    overlap_end = min(end_min, range_end_min)
    return max(0, overlap_end - overlap_start)


def calc_work_hours(clock_in: str, clock_out: str, cfg, work_date=None, calendar_day_type=None):
    in_min = _time_to_minutes(clock_in)
    out_min = _time_to_minutes(clock_out)

    if out_min <= in_min:
        raw_minutes = (24 * 60 - in_min) + out_min
    else:
        raw_minutes = out_min - in_min

    break_min = int(cfg.get("BREAK_HOURS", 1.0) * 60)
    worked_min = max(0, raw_minutes - break_min)
    total_hours = round(worked_min / 60, 2)

    if calendar_day_type in CALENDAR_DAY_TYPES:
        is_holiday_work = calendar_day_type in LEAVE_DAY_TYPES
    else:
        is_holiday_work = False
        if work_date:
            if isinstance(work_date, str):
                work_date = _parse_date(work_date)

            if work_date.weekday() >= 5:
                is_holiday_work = True

            holidays_2026 = cfg.get("PUBLIC_HOLIDAYS_2026", [])
            if work_date.strftime("%Y-%m-%d") in holidays_2026:
                is_holiday_work = True

    std_hours = cfg.get("STANDARD_WORK_HOURS", 8.0)

    # 유급/무급 휴일 구분
    is_paid_holiday = False
    if calendar_day_type == "paid_leave":
        is_paid_holiday = True
    elif calendar_day_type not in CALENDAR_DAY_TYPES and work_date:
        if isinstance(work_date, str):
            work_date = _parse_date(work_date)
        holidays_2026 = cfg.get("PUBLIC_HOLIDAYS_2026", [])
        if work_date.weekday() == 6 or work_date.strftime("%Y-%m-%d") in holidays_2026:
            is_paid_holiday = True

    if is_holiday_work:
        if is_paid_holiday:
            # 유급휴일: 8시간 이내 → holiday_work_hours, 8시간 초과 → ot_hours
            holiday_work_hours = round(min(total_hours, std_hours), 2)
            ot_hours = round(max(0, total_hours - std_hours), 2)
        else:
            # 무급휴일: 전체가 동일 배율 → holiday_work_hours
            holiday_work_hours = total_hours
            ot_hours = 0.0
    else:
        ot_hours = round(max(0, total_hours - std_hours), 2)
        holiday_work_hours = 0.0

    night_start = cfg.get("NIGHT_START", 22) * 60
    night_end = cfg.get("NIGHT_END", 6) * 60

    if out_min <= in_min:
        night_min1 = _minutes_in_range(in_min, 24 * 60, night_start, 24 * 60)
        night_min2 = _minutes_in_range(0, out_min, 0, night_end)
        night_total = night_min1 + night_min2
    else:
        night_total = _minutes_in_range(in_min, out_min, night_start, night_end)

    is_night_shift = (in_min >= 15 * 60 or in_min < night_end)
    night_break = break_min if is_night_shift else 0
    night_calc = max(0, night_total - night_break)
    night_hours = round(night_calc / 60, 2)

    return total_hours, ot_hours, night_hours, holiday_work_hours


def _get_cfg():
    c = current_app.config
    return {
        "STANDARD_WORK_HOURS": c.get("STANDARD_WORK_HOURS", 8.0),
        "BREAK_HOURS": c.get("BREAK_HOURS", 1.0),
        "NIGHT_START": c.get("NIGHT_START", 22),
        "NIGHT_END": c.get("NIGHT_END", 6),
        "PUBLIC_HOLIDAYS_2026": c.get("PUBLIC_HOLIDAYS_2026", []),
    }


def _default_day_type(work_date, cfg):
    holidays_2026 = cfg.get("PUBLIC_HOLIDAYS_2026", [])
    if work_date.weekday() == 6:
        return "paid_leave"
    if work_date.weekday() == 5:
        return "unpaid_leave"
    if work_date.strftime("%Y-%m-%d") in holidays_2026:
        return "paid_leave"
    return "workday"


def _calendar_override_type(work_date):
    row = OperationCalendarDay.query.filter_by(work_date=work_date).first()
    if not row:
        return None
    return row.day_type


def _effective_day_type(work_date, cfg):
    override = _calendar_override_type(work_date)
    if override in CALENDAR_DAY_TYPES:
        return override
    return _default_day_type(work_date, cfg)
