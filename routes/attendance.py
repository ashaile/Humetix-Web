import logging
import re
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
from sqlalchemy.exc import IntegrityError

from models import AttendanceRecord, Employee, db

logger = logging.getLogger(__name__)

attendance_bp = Blueprint("attendance", __name__)

ALLOWED_WORK_TYPES = {"normal", "night", "annual", "absent", "holiday", "early"}
TIME_REQUIRED_TYPES = {"normal", "night"}


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


def calc_work_hours(clock_in: str, clock_out: str, cfg, work_date=None):
    in_min = _time_to_minutes(clock_in)
    out_min = _time_to_minutes(clock_out)

    if out_min <= in_min:
        raw_minutes = (24 * 60 - in_min) + out_min
    else:
        raw_minutes = out_min - in_min

    break_min = int(cfg.get("BREAK_HOURS", 1.0) * 60)
    worked_min = max(0, raw_minutes - break_min)
    total_hours = round(worked_min / 60, 2)

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

    night_calc = max(0, night_total - break_min)
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
    employee = Employee.query.filter_by(
        name=emp_name, birth_date=birth_date, is_active=True
    ).first()
    if not employee:
        return jsonify({"error": "등록된 재직 직원만 입력할 수 있습니다."}), 403

    try:
        work_date = _parse_date(str(data["work_date"]).strip())
    except ValueError:
        return jsonify({"error": "work_date format must be YYYY-MM-DD"}), 400

    work_type = str(data.get("work_type", "normal")).strip()
    if work_type not in ALLOWED_WORK_TYPES:
        return jsonify({"error": f"Invalid work_type: {work_type}"}), 400

    exists = AttendanceRecord.query.filter_by(
        employee_id=employee.id,
        work_date=work_date,
    ).first()
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
        total_hours, ot_hours, night_hours, holiday_hours = calc_work_hours(
            clock_in, clock_out, _get_cfg(), work_date=work_date
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

    records = query.order_by(AttendanceRecord.work_date.asc()).all()
    return jsonify({"records": [r.to_dict() for r in records]})


@attendance_bp.route("/attendance")
def attendance_page():
    today = date.today()
    today_records = (
        AttendanceRecord.query.filter(AttendanceRecord.work_date == today)
        .order_by(AttendanceRecord.emp_name.asc())
        .all()
    )
    return render_template("attendance.html", records=today_records, today=today)


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

    records = query.order_by(AttendanceRecord.work_date.desc()).all()

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

    records = query.order_by(AttendanceRecord.work_date.asc()).all()

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
        ws.cell(row=i, column=7, value=rec.work_type)
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

    record = AttendanceRecord.query.get_or_404(record_id)
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "JSON body required"}), 400

    if "employee_id" in data:
        employee_id = str(data.get("employee_id", "")).strip()
        if not employee_id.isdigit():
            return jsonify({"error": "employee_id must be integer"}), 400
        employee = Employee.query.get(int(employee_id))
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
        total, ot, night, holiday = calc_work_hours(
            record.clock_in,
            record.clock_out,
            _get_cfg(),
            work_date=record.work_date,
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

    record = AttendanceRecord.query.get_or_404(record_id)
    try:
        db.session.delete(record)
        db.session.commit()
        return jsonify({"success": True})
    except Exception as exc:
        db.session.rollback()
        logger.error("Attendance delete error: %s", exc)
        return jsonify({"error": "DELETE failed"}), 500
