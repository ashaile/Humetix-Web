import logging
import re
from datetime import datetime
from io import BytesIO

from flask import (
    Blueprint,
    current_app,
    jsonify,
    render_template,
    request,
    send_file,
)
from models import Employee, Payslip, db
from routes.utils import require_admin, validate_month as _validate_month
from services.payslip_service import ALLOWED_SALARY_MODES, compute_payslips

logger = logging.getLogger(__name__)

payslip_bp = Blueprint("payslip", __name__)


@payslip_bp.route("/admin/payslip")
@require_admin
def admin_payslip():
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
@require_admin
def generate_payslips():
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

    try:
        result = compute_payslips(month, salary_mode)
    except Exception as exc:
        db.session.rollback()
        logger.error("Payslip generate error: %s", exc)
        return jsonify({"error": "급여 생성 중 오류가 발생했습니다."}), 500

    if isinstance(result, str):
        return jsonify({"error": result}), 404

    created, updated = result
    return jsonify({"success": True, "created": created, "updated": updated})


@payslip_bp.route("/admin/payslip/<int:payslip_id>", methods=["DELETE"])
@require_admin
def delete_payslip(payslip_id: int):
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
@require_admin
def delete_payslips_by_month():
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


def _generate_payslip_pdf(payslips):
    """급여명세서 PDF 생성 (공통 헬퍼). BytesIO 반환."""
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
    return buf


@payslip_bp.route("/admin/payslip/pdf")
@require_admin
def payslip_pdf():
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

    buf = _generate_payslip_pdf(payslips)
    return send_file(
        buf,
        as_attachment=True,
        download_name=f"급여명세서_{month}.pdf",
        mimetype="application/pdf",
    )


@payslip_bp.route("/admin/payslip/excel")
@require_admin
def payslip_excel():
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


# ── Public payslip lookup ──


@payslip_bp.route("/payslip", methods=["GET", "POST"])
def payslip_lookup():
    if request.method == "GET":
        return render_template("payslip_lookup.html")

    birth_date = request.form.get("birth_date", "").strip()
    emp_name = request.form.get("emp_name", "").strip()

    errors = []
    if not re.fullmatch(r"\d{6}", birth_date):
        errors.append("생년월일은 YYMMDD 6자리 숫자여야 합니다.")
    if not emp_name:
        errors.append("이름을 입력해주세요.")
    if errors:
        return render_template("payslip_lookup.html", errors=errors, form=request.form)

    employee = Employee.query.filter_by(
        name=emp_name, birth_date=birth_date, is_active=True
    ).first()
    if not employee:
        return render_template(
            "payslip_lookup.html",
            errors=["등록된 재직 직원이 아닙니다."],
            form=request.form,
        )

    payslips = (
        Payslip.query.filter_by(employee_id=employee.id)
        .order_by(Payslip.month.desc())
        .all()
    )
    return render_template(
        "payslip_lookup.html",
        payslips=payslips,
        employee=employee,
        form=request.form,
    )


@payslip_bp.route("/payslip/pdf")
def payslip_public_pdf():
    birth_date = request.args.get("birth_date", "").strip()
    emp_name = request.args.get("emp_name", "").strip()
    month = request.args.get("month", "").strip()

    if not (re.fullmatch(r"\d{6}", birth_date) and emp_name and _validate_month(month)):
        return jsonify({"error": "잘못된 요청입니다."}), 400

    employee = Employee.query.filter_by(
        name=emp_name, birth_date=birth_date, is_active=True
    ).first()
    if not employee:
        return jsonify({"error": "직원 정보를 확인할 수 없습니다."}), 403

    payslip = Payslip.query.filter_by(
        employee_id=employee.id, month=month
    ).first()
    if not payslip:
        return jsonify({"error": "해당 월 급여 데이터가 없습니다."}), 404

    buf = _generate_payslip_pdf([payslip])
    return send_file(
        buf,
        as_attachment=True,
        download_name=f"급여명세서_{month}_{emp_name}.pdf",
        mimetype="application/pdf",
    )
