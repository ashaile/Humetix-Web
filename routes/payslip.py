import logging
from datetime import datetime
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
from sqlalchemy import func

from models import AdvanceRequest, AttendanceRecord, Payslip, db
from routes.utils import validate_month as _validate_month

logger = logging.getLogger(__name__)

payslip_bp = Blueprint("payslip", __name__)

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


@payslip_bp.route("/admin/payslip")
def admin_payslip():
    if not session.get("is_admin"):
        return redirect(url_for("auth.login"))

    month = request.args.get("month", datetime.now().strftime("%Y-%m"))
    if not _validate_month(month):
        month = datetime.now().strftime("%Y-%m")

    payslips = Payslip.query.filter(Payslip.month == month).order_by(Payslip.emp_name.asc()).all()

    cfg = current_app.config
    return render_template(
        "admin_payslip.html",
        payslips=payslips,
        month=month,
        salary_mode=cfg.get("SALARY_MODE", "standard"),
        hourly_wage=cfg.get("HOURLY_WAGE", 10320),
    )


@payslip_bp.route("/admin/payslip/generate", methods=["POST"])
def generate_payslips():
    if not session.get("is_admin"):
        return jsonify({"error": "권한이 없습니다."}), 401

    payload = request.get_json(silent=True) or {}
    month = (request.form.get("month") or payload.get("month") or "").strip()
    if not _validate_month(month):
        return jsonify({"error": "month (YYYY-MM) is required"}), 400

    salary_mode = (
        request.form.get("salary_mode")
        or payload.get("salary_mode")
        or request.args.get("salary_mode")
        or current_app.config.get("SALARY_MODE", "standard")
    )
    if salary_mode not in ALLOWED_SALARY_MODES:
        return jsonify({"error": f"invalid salary_mode: {salary_mode}"}), 400

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
        return jsonify({"error": f"{month} 근태 기록이 없습니다."}), 404

    created = 0
    updated = 0
    try:
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
        return jsonify({"success": True, "created": created, "updated": updated})
    except Exception as exc:
        db.session.rollback()
        logger.error("Payslip generate error: %s", exc)
        return jsonify({"error": "급여 생성 중 오류가 발생했습니다."}), 500


@payslip_bp.route("/admin/payslip/<int:payslip_id>", methods=["DELETE"])
def delete_payslip(payslip_id: int):
    if not session.get("is_admin"):
        return jsonify({"error": "권한이 없습니다."}), 401

    payslip = db.session.get(Payslip, payslip_id)
    if not payslip:
        return jsonify({"error": "급여명세서를 찾을 수 없습니다."}), 404

    try:
        db.session.delete(payslip)
        db.session.commit()
        return jsonify({"success": True, "deleted": 1, "id": payslip_id})
    except Exception as exc:
        db.session.rollback()
        logger.error("Payslip delete error: %s", exc)
        return jsonify({"error": "급여명세서 삭제 중 오류가 발생했습니다."}), 500


@payslip_bp.route("/admin/payslip/delete-month", methods=["POST"])
def delete_payslips_by_month():
    if not session.get("is_admin"):
        return jsonify({"error": "권한이 없습니다."}), 401

    payload = request.get_json(silent=True) or {}
    month = (request.form.get("month") or payload.get("month") or "").strip()
    if not _validate_month(month):
        return jsonify({"error": "month (YYYY-MM) is required"}), 400

    try:
        deleted_count = (
            Payslip.query.filter(Payslip.month == month).delete(synchronize_session=False)
        )
        db.session.commit()
        return jsonify({"success": True, "deleted": deleted_count, "month": month})
    except Exception as exc:
        db.session.rollback()
        logger.error("Payslip month delete error: %s", exc)
        return jsonify({"error": "월 급여명세서 삭제 중 오류가 발생했습니다."}), 500


@payslip_bp.route("/admin/payslip/pdf")
def payslip_pdf():
    if not session.get("is_admin"):
        return redirect(url_for("auth.login"))

    month = request.args.get("month", datetime.now().strftime("%Y-%m"))
    if not _validate_month(month):
        return jsonify({"error": "invalid month format"}), 400

    employee_id = request.args.get("employee_id") or request.args.get("emp_id")
    query = Payslip.query.filter(Payslip.month == month)
    if employee_id:
        if not str(employee_id).isdigit():
            return jsonify({"error": "employee_id must be integer"}), 400
        query = query.filter(Payslip.employee_id == int(employee_id))

    payslips = query.order_by(Payslip.emp_name.asc()).all()
    if not payslips:
        return jsonify({"error": "해당 월 급여 데이터가 없습니다."}), 404

    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfgen import canvas

    import os

    buf = BytesIO()
    pdf = canvas.Canvas(buf, pagesize=A4)
    width, height = A4

    font_name = "Helvetica"
    for font_path in [
        "C:/Windows/Fonts/malgun.ttf",
        "C:/Windows/Fonts/gulim.ttc",
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    ]:
        if os.path.exists(font_path):
            try:
                pdfmetrics.registerFont(TTFont("KoreanFont", font_path))
                font_name = "KoreanFont"
                break
            except Exception:
                continue

    hourly = current_app.config.get("HOURLY_WAGE", 10320)

    for payslip in payslips:
        y = height - 40 * mm

        pdf.setFont(font_name, 16)
        pdf.drawString(30 * mm, y, "HUMETIX Co., Ltd.")
        y -= 10 * mm
        pdf.setFont(font_name, 20)
        pdf.drawString(30 * mm, y, f"{payslip.month} 급여명세서")
        y -= 12 * mm

        pdf.setFont(font_name, 11)
        pdf.drawString(
            30 * mm,
            y,
            f"성명: {payslip.emp_name}    부서: {payslip.dept}    시급: {hourly:,}원",
        )
        y -= 8 * mm
        mode_label = "209h 고정" if payslip.salary_mode == "standard" else "실근무시간"
        pdf.drawString(
            30 * mm,
            y,
            f"계산방식: {mode_label}    총근무: {payslip.total_work_hours}h",
        )
        y -= 12 * mm

        pdf.setFont(font_name, 12)
        pdf.drawString(30 * mm, y, "지급 내역")
        y -= 8 * mm
        pdf.setFont(font_name, 11)
        earnings = [
            ("기본급", payslip.base_salary),
            (f"잔업수당 ({payslip.ot_hours}h x {hourly:,} x 1.5)", payslip.ot_pay),
            (f"심야수당 ({payslip.night_hours}h x {hourly:,} x 0.5)", payslip.night_pay),
            (
                f"휴일수당 ({payslip.holiday_hours}h x {hourly:,} x 1.5)",
                payslip.holiday_pay,
            ),
            ("총지급액", payslip.gross),
        ]
        for label, value in earnings:
            pdf.drawString(35 * mm, y, label)
            pdf.drawRightString(170 * mm, y, f"{value:,}원")
            y -= 7 * mm

        y -= 5 * mm
        pdf.setFont(font_name, 12)
        pdf.drawString(30 * mm, y, "공제 내역")
        y -= 8 * mm
        pdf.setFont(font_name, 11)
        deductions = [
            ("소득세 (3.3%)", payslip.tax),
            ("4대보험 (9.7%)", payslip.insurance),
        ]
        if payslip.advance_deduction > 0:
            deductions.append(("가불 차감", payslip.advance_deduction))
        for label, value in deductions:
            pdf.drawString(35 * mm, y, label)
            pdf.drawRightString(170 * mm, y, f"-{value:,}원")
            y -= 7 * mm

        y -= 8 * mm
        pdf.setFont(font_name, 14)
        pdf.drawString(30 * mm, y, "실수령액")
        pdf.drawRightString(170 * mm, y, f"{payslip.net:,}원")

        pdf.showPage()

    pdf.save()
    buf.seek(0)
    return send_file(
        buf,
        as_attachment=True,
        download_name=f"급여명세서_{month}.pdf",
        mimetype="application/pdf",
    )


@payslip_bp.route("/admin/payslip/excel")
def payslip_excel():
    if not session.get("is_admin"):
        return redirect(url_for("auth.login"))

    from openpyxl import Workbook
    from openpyxl.styles import Font

    month = request.args.get("month", datetime.now().strftime("%Y-%m"))
    if not _validate_month(month):
        return jsonify({"error": "invalid month format"}), 400

    payslips = Payslip.query.filter(Payslip.month == month).order_by(Payslip.emp_name.asc()).all()

    wb = Workbook()
    ws = wb.active
    ws.title = f"{month} 급여"

    headers = [
        "직원ID",
        "이름",
        "부서",
        "계산방식",
        "총근무(h)",
        "잔업(h)",
        "야간(h)",
        "휴일(h)",
        "기본급",
        "잔업수당",
        "야간수당",
        "휴일수당",
        "총지급",
        "소득세",
        "4대보험",
        "가불차감",
        "실수령액",
    ]
    bold = Font(bold=True)
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = bold

    for i, payslip in enumerate(payslips, 2):
        mode_label = "209h고정" if payslip.salary_mode == "standard" else "실근무"
        values = [
            payslip.employee_id,
            payslip.emp_name,
            payslip.dept,
            mode_label,
            payslip.total_work_hours,
            payslip.ot_hours,
            payslip.night_hours,
            payslip.holiday_hours,
            payslip.base_salary,
            payslip.ot_pay,
            payslip.night_pay,
            payslip.holiday_pay,
            payslip.gross,
            payslip.tax,
            payslip.insurance,
            payslip.advance_deduction,
            payslip.net,
        ]
        for col, value in enumerate(values, 1):
            ws.cell(row=i, column=col, value=value)

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return send_file(
        buf,
        as_attachment=True,
        download_name=f"급여명세서_{month}.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
