import logging
import re
from calendar import monthrange
from datetime import date, datetime
from io import BytesIO

from flask import (
    Blueprint,
    current_app,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from sqlalchemy.exc import IntegrityError, OperationalError

from models import AttendanceRecord, Employee, OperationCalendarDay, db

logger = logging.getLogger(__name__)

attendance_bp = Blueprint("attendance", __name__)

ALLOWED_WORK_TYPES = {"normal", "night", "annual", "absent", "holiday", "early"}
TIME_REQUIRED_TYPES = {"normal", "night"}
CALENDAR_DAY_TYPES = {"workday", "paid_leave", "unpaid_leave"}
LEAVE_DAY_TYPES = {"paid_leave", "unpaid_leave"}


def _parse_date(value: str):
    return datetime.strptime(value, "%Y-%m-%d").date()


def _validate_month(value: str) -> bool:
    if not value or not re.fullmatch(r"\d{4}-\d{2}", value):
        return False
    year, month = map(int, value.split("-"))
    return 2000 <= year <= 2100 and 1 <= month <= 12


def _month_bounds(month_text: str):
    year, month = map(int, month_text.split("-"))
    last_day = monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last_day)


def _default_day_type(work_date: date, cfg) -> str:
    holidays_2026 = cfg.get("PUBLIC_HOLIDAYS_2026", [])
    if work_date.weekday() == 6:
        return "paid_leave"
    if work_date.weekday() == 5:
        return "unpaid_leave"
    if work_date.strftime("%Y-%m-%d") in holidays_2026:
        return "paid_leave"
    return "workday"


def _calendar_override_type(work_date: date):
    row = OperationCalendarDay.query.filter_by(work_date=work_date).first()
    if not row:
        return None
    return row.day_type


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

    if is_holiday_work:
        ot_hours = 0.0
        holiday_work_hours = total_hours
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

    # 한국 노동법 기준 휴게시간 처리:
    # - 주간 휴게(12:30~13:30): 야간 구간(22~06시)과 겹치지 않으므로 야간 차감 없음
    # - 야간 휴게(00:00~01:00): 야간 구간 내에 위치하므로 야간 시간에서 차감
    # 15:00 이후 시작 또는 새벽(06:00 이전) 시작을 야간 근무로 판단
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


def _effective_day_type(work_date: date, cfg):
    override = _calendar_override_type(work_date)
    if override in CALENDAR_DAY_TYPES:
        return override
    return _default_day_type(work_date, cfg)


def _db_not_ready_message():
    return (
        "데이터베이스 초기화가 필요합니다. "
        "프로젝트 폴더에서 python fix_db.py 실행 후 서버를 재시작하세요."
    )


def _db_not_ready_json():
    return jsonify({"error": _db_not_ready_message()}), 503


def _db_not_ready_page():
    return render_template(
        "error.html",
        error_code="503",
        error_message="데이터베이스 초기화 필요",
        error_description=_db_not_ready_message(),
    ), 503


@attendance_bp.route("/api/attendance", methods=["POST"])
def create_attendance():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "JSON body required"}), 400

    required = ["emp_name", "birth_date", "work_date"]
    missing = [field for field in required if not data.get(field)]
    if missing:
        return jsonify({"error": f"Missing fields: {', '.join(missing)}"}), 400

    birth_date = str(data["birth_date"]).strip()
    if not re.fullmatch(r"\d{6}", birth_date):
        return jsonify({"error": "birth_date must be YYMMDD"}), 400

    emp_name = str(data["emp_name"]).strip()
    try:
        employee = Employee.query.filter_by(
            name=emp_name, birth_date=birth_date, is_active=True
        ).first()
    except OperationalError as exc:
        logger.error("Attendance create query failed: %s", exc)
        return _db_not_ready_json()

    if not employee:
        return jsonify({"error": "등록된 재직 직원만 입력할 수 있습니다."}), 403

    try:
        work_date = _parse_date(str(data["work_date"]).strip())
    except ValueError:
        return jsonify({"error": "work_date format must be YYYY-MM-DD"}), 400

    work_type = str(data.get("work_type", "normal")).strip()
    if work_type not in ALLOWED_WORK_TYPES:
        return jsonify({"error": f"Invalid work_type: {work_type}"}), 400

    try:
        exists = AttendanceRecord.query.filter_by(
            employee_id=employee.id,
            work_date=work_date,
        ).first()
    except OperationalError as exc:
        logger.error("Attendance duplicate-check query failed: %s", exc)
        return _db_not_ready_json()

    if exists:
        return jsonify({"error": "같은 날짜의 근태 기록이 이미 존재합니다."}), 409

    clock_in = None
    clock_out = None
    total_hours = 0.0
    ot_hours = 0.0
    night_hours = 0.0
    holiday_hours = 0.0

    if work_type in TIME_REQUIRED_TYPES:
        clock_in = str(data.get("clock_in", "")).strip()
        clock_out = str(data.get("clock_out", "")).strip()
        if not (_validate_hhmm(clock_in) and _validate_hhmm(clock_out)):
            return jsonify({"error": "clock_in/clock_out format must be HH:MM"}), 400
        cfg = _get_cfg()
        try:
            day_type = _effective_day_type(work_date, cfg)
        except OperationalError as exc:
            logger.error("Attendance calendar lookup failed: %s", exc)
            return _db_not_ready_json()
        total_hours, ot_hours, night_hours, holiday_hours = calc_work_hours(
            clock_in,
            clock_out,
            cfg,
            work_date=work_date,
            calendar_day_type=day_type,
        )

    record = AttendanceRecord(
        employee_id=employee.id,
        birth_date=employee.birth_date,
        emp_name=employee.name,
        dept=str(data.get("dept", "")).strip(),
        work_date=work_date,
        clock_in=clock_in,
        clock_out=clock_out,
        work_type=work_type,
        total_work_hours=total_hours,
        overtime_hours=ot_hours,
        night_hours=night_hours,
        holiday_work_hours=holiday_hours,
    )

    try:
        db.session.add(record)
        db.session.commit()
        return jsonify({"success": True, "record": record.to_dict()}), 201
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "같은 날짜의 근태 기록이 이미 존재합니다."}), 409
    except Exception as exc:
        db.session.rollback()
        logger.error("Attendance create error: %s", exc)
        return jsonify({"error": "서버 오류가 발생했습니다."}), 500


@attendance_bp.route("/api/attendance", methods=["GET"])
def list_attendance():
    query = AttendanceRecord.query

    employee_id = request.args.get("employee_id") or request.args.get("emp_id")
    if employee_id:
        if not str(employee_id).isdigit():
            return jsonify({"error": "employee_id must be integer"}), 400
        query = query.filter(AttendanceRecord.employee_id == int(employee_id))

    emp_name = request.args.get("emp_name", "").strip()
    if emp_name:
        query = query.filter(AttendanceRecord.emp_name.contains(emp_name))

    start = request.args.get("start_date")
    if start:
        try:
            query = query.filter(AttendanceRecord.work_date >= _parse_date(start))
        except ValueError:
            return jsonify({"error": "start_date format must be YYYY-MM-DD"}), 400

    end = request.args.get("end_date")
    if end:
        try:
            query = query.filter(AttendanceRecord.work_date <= _parse_date(end))
        except ValueError:
            return jsonify({"error": "end_date format must be YYYY-MM-DD"}), 400

    try:
        records = query.order_by(AttendanceRecord.work_date.asc()).all()
    except OperationalError as exc:
        logger.error("Attendance list query failed: %s", exc)
        return _db_not_ready_json()

    return jsonify({"records": [r.to_dict() for r in records]})


@attendance_bp.route("/attendance")
def attendance_page():
    today = date.today()
    try:
        today_records = (
            AttendanceRecord.query.filter(AttendanceRecord.work_date == today)
            .order_by(AttendanceRecord.emp_name.asc())
            .all()
        )
    except OperationalError as exc:
        logger.error("Attendance page query failed: %s", exc)
        return _db_not_ready_page()

    return render_template("attendance.html", records=today_records, today=today)


@attendance_bp.route("/admin/attendance-calendar")
def admin_attendance_calendar():
    if not session.get("is_admin"):
        return redirect(url_for("auth.login"))

    month_text = request.args.get("month", date.today().strftime("%Y-%m"))
    if not _validate_month(month_text):
        month_text = date.today().strftime("%Y-%m")

    start_date, end_date = _month_bounds(month_text)
    try:
        overrides = (
            OperationCalendarDay.query.filter(
                OperationCalendarDay.work_date >= start_date,
                OperationCalendarDay.work_date <= end_date,
            )
            .order_by(OperationCalendarDay.work_date.asc())
            .all()
        )
    except OperationalError as exc:
        logger.error("Attendance calendar query failed: %s", exc)
        return _db_not_ready_page()

    override_map = {row.work_date: row for row in overrides}

    cfg = _get_cfg()
    days = []
    day = start_date.day
    while day <= end_date.day:
        current = date(start_date.year, start_date.month, day)
        default_type = _default_day_type(current, cfg)
        override = override_map.get(current)
        effective_type = override.day_type if override else default_type
        days.append(
            {
                "date": current,
                "default_type": default_type,
                "override_type": override.day_type if override else "default",
                "effective_type": effective_type,
                "note": override.note if override else "",
            }
        )
        day += 1

    return render_template(
        "admin_attendance_calendar.html",
        month=month_text,
        days=days,
    )


@attendance_bp.route("/admin/attendance-calendar", methods=["POST"])
def save_attendance_calendar():
    if not session.get("is_admin"):
        return redirect(url_for("auth.login"))

    work_date_text = (request.form.get("work_date") or "").strip()
    day_type = (request.form.get("day_type") or "").strip()
    note = (request.form.get("note") or "").strip()[:200]
    month_text = (request.form.get("month") or "").strip()

    if not _validate_month(month_text):
        month_text = date.today().strftime("%Y-%m")

    try:
        work_date = _parse_date(work_date_text)
    except ValueError:
        return redirect(url_for("attendance.admin_attendance_calendar", month=month_text))

    try:
        row = OperationCalendarDay.query.filter_by(work_date=work_date).first()
    except OperationalError as exc:
        logger.error("Attendance calendar write query failed: %s", exc)
        return _db_not_ready_page()
    if day_type == "default":
        if row:
            db.session.delete(row)
            try:
                db.session.commit()
            except OperationalError as exc:
                db.session.rollback()
                logger.error("Attendance calendar delete commit failed: %s", exc)
                return _db_not_ready_page()
        return redirect(url_for("attendance.admin_attendance_calendar", month=month_text))

    if day_type not in CALENDAR_DAY_TYPES:
        return redirect(url_for("attendance.admin_attendance_calendar", month=month_text))

    if row:
        row.day_type = day_type
        row.note = note
    else:
        row = OperationCalendarDay(
            work_date=work_date,
            day_type=day_type,
            note=note,
        )
        db.session.add(row)
    try:
        db.session.commit()
    except OperationalError as exc:
        db.session.rollback()
        logger.error("Attendance calendar save commit failed: %s", exc)
        return _db_not_ready_page()

    return redirect(url_for("attendance.admin_attendance_calendar", month=month_text))


@attendance_bp.route("/admin/attendance")
def admin_attendance():
    if not session.get("is_admin"):
        return redirect(url_for("auth.login"))

    start = request.args.get("start_date", "")
    end = request.args.get("end_date", "")
    emp_name = request.args.get("emp_name", "")

    query = AttendanceRecord.query
    if start:
        try:
            query = query.filter(AttendanceRecord.work_date >= _parse_date(start))
        except ValueError:
            start = ""
    if end:
        try:
            query = query.filter(AttendanceRecord.work_date <= _parse_date(end))
        except ValueError:
            end = ""
    if emp_name:
        query = query.filter(AttendanceRecord.emp_name.contains(emp_name))

    try:
        records = query.order_by(AttendanceRecord.work_date.desc()).all()
    except OperationalError as exc:
        logger.error("Admin attendance query failed: %s", exc)
        return _db_not_ready_page()

    today = date.today()
    stats_source = records
    stats = {
        "total": len(stats_source),
        "day": len([r for r in stats_source if r.work_type == "normal"]),
        "night": len([r for r in stats_source if r.work_type == "night"]),
        "total_work": round(sum(r.total_work_hours for r in stats_source), 1),
        "total_night": round(sum(r.night_hours for r in stats_source), 1),
        "total_ot": round(sum(r.overtime_hours for r in stats_source), 1),
        "total_holiday": round(sum((r.holiday_work_hours or 0) for r in stats_source), 1),
    }

    return render_template(
        "admin_attendance.html",
        records=records,
        start_date=start,
        end_date=end,
        emp_name=emp_name,
        stats=stats,
        today=today,
    )


@attendance_bp.route("/admin/attendance/excel")
def attendance_excel():
    if not session.get("is_admin"):
        return redirect(url_for("auth.login"))

    from openpyxl import Workbook
    from openpyxl.styles import Font

    start = request.args.get("start_date", "")
    end = request.args.get("end_date", "")
    emp_name = request.args.get("emp_name", "")

    query = AttendanceRecord.query
    if start:
        try:
            query = query.filter(AttendanceRecord.work_date >= _parse_date(start))
        except ValueError:
            start = ""
    if end:
        try:
            query = query.filter(AttendanceRecord.work_date <= _parse_date(end))
        except ValueError:
            end = ""
    if emp_name:
        query = query.filter(AttendanceRecord.emp_name.contains(emp_name))

    try:
        records = query.order_by(AttendanceRecord.work_date.asc()).all()
    except OperationalError as exc:
        logger.error("Attendance excel query failed: %s", exc)
        return _db_not_ready_page()

    wb = Workbook()
    ws = wb.active
    ws.title = "근태기록"

    headers = [
        "직원ID",
        "이름",
        "부서",
        "날짜",
        "출근",
        "퇴근",
        "구분",
        "총근무(h)",
        "잔업(h)",
        "야간(h)",
        "휴일(h)",
    ]
    bold = Font(bold=True)
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = bold

    work_type_labels = {
        "normal": "주간",
        "night": "야간",
        "annual": "연차",
        "absent": "결근",
        "holiday": "휴무",
        "early": "조퇴",
    }

    for i, rec in enumerate(records, 2):
        ws.cell(row=i, column=1, value=rec.employee_id)
        ws.cell(row=i, column=2, value=rec.emp_name)
        ws.cell(row=i, column=3, value=rec.dept)
        ws.cell(
            row=i,
            column=4,
            value=rec.work_date.strftime("%Y-%m-%d") if rec.work_date else "",
        )
        ws.cell(row=i, column=5, value=rec.clock_in)
        ws.cell(row=i, column=6, value=rec.clock_out)
        ws.cell(row=i, column=7, value=work_type_labels.get(rec.work_type, rec.work_type))
        ws.cell(row=i, column=8, value=rec.total_work_hours)
        ws.cell(row=i, column=9, value=rec.overtime_hours)
        ws.cell(row=i, column=10, value=rec.night_hours)
        ws.cell(row=i, column=11, value=rec.holiday_work_hours or 0)

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return send_file(
        buf,
        as_attachment=True,
        download_name=f"근태기록_{start or 'all'}_{end or 'all'}.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@attendance_bp.route("/api/attendance/<int:record_id>", methods=["PUT"])
def update_attendance(record_id):
    if not session.get("is_admin"):
        return jsonify({"error": "Unauthorized"}), 403

    record = db.get_or_404(AttendanceRecord, record_id)
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "JSON body required"}), 400

    if "employee_id" in data:
        employee_id = str(data.get("employee_id", "")).strip()
        if not employee_id.isdigit():
            return jsonify({"error": "employee_id must be integer"}), 400
        employee = db.session.get(Employee, int(employee_id))
        if not employee:
            return jsonify({"error": "employee not found"}), 404
        record.employee_id = employee.id
        record.emp_name = employee.name
        record.birth_date = employee.birth_date

    if "emp_name" in data or "birth_date" in data:
        name = str(data.get("emp_name", record.emp_name)).strip()
        birth = str(data.get("birth_date", record.birth_date)).strip()
        employee = Employee.query.filter_by(name=name, birth_date=birth).first()
        if employee:
            record.employee_id = employee.id
            record.emp_name = employee.name
            record.birth_date = employee.birth_date

    if "dept" in data:
        record.dept = str(data.get("dept", "")).strip()

    if "work_date" in data:
        try:
            record.work_date = _parse_date(str(data["work_date"]).strip())
        except ValueError:
            return jsonify({"error": "work_date format must be YYYY-MM-DD"}), 400

    if "work_type" in data:
        work_type = str(data["work_type"]).strip()
        if work_type not in ALLOWED_WORK_TYPES:
            return jsonify({"error": f"Invalid work_type: {work_type}"}), 400
        record.work_type = work_type

    if "clock_in" in data:
        val = str(data.get("clock_in") or "").strip()
        record.clock_in = val or None
    if "clock_out" in data:
        val = str(data.get("clock_out") or "").strip()
        record.clock_out = val or None

    duplicate = AttendanceRecord.query.filter(
        AttendanceRecord.employee_id == record.employee_id,
        AttendanceRecord.work_date == record.work_date,
        AttendanceRecord.id != record.id,
    ).first()
    if duplicate:
        return jsonify({"error": "같은 날짜의 근태 기록이 이미 존재합니다."}), 409

    if record.work_type in TIME_REQUIRED_TYPES:
        if not (_validate_hhmm(record.clock_in or "") and _validate_hhmm(record.clock_out or "")):
            return jsonify({"error": "clock_in/clock_out format must be HH:MM"}), 400
        cfg = _get_cfg()
        try:
            day_type = _effective_day_type(record.work_date, cfg)
        except OperationalError as exc:
            logger.error("Attendance calendar lookup failed during update: %s", exc)
            return _db_not_ready_json()
        total, ot, night, holiday = calc_work_hours(
            record.clock_in,
            record.clock_out,
            cfg,
            work_date=record.work_date,
            calendar_day_type=day_type,
        )
        record.total_work_hours = total
        record.overtime_hours = ot
        record.night_hours = night
        record.holiday_work_hours = holiday
    else:
        record.clock_in = None
        record.clock_out = None
        record.total_work_hours = 0.0
        record.overtime_hours = 0.0
        record.night_hours = 0.0
        record.holiday_work_hours = 0.0

    try:
        db.session.commit()
        return jsonify({"success": True, "record": record.to_dict()})
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "중복 근태 기록입니다."}), 409
    except Exception as exc:
        db.session.rollback()
        logger.error("Attendance update error: %s", exc)
        return jsonify({"error": "서버 오류가 발생했습니다."}), 500


@attendance_bp.route("/api/attendance/<int:record_id>", methods=["DELETE"])
def delete_attendance(record_id):
    if not session.get("is_admin"):
        return jsonify({"error": "Unauthorized"}), 403

    record = db.get_or_404(AttendanceRecord, record_id)
    try:
        db.session.delete(record)
        db.session.commit()
        return jsonify({"success": True})
    except Exception as exc:
        db.session.rollback()
        logger.error("Attendance delete error: %s", exc)
        return jsonify({"error": "DELETE failed"}), 500
