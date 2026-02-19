import logging
from datetime import datetime
from flask import Blueprint, request, jsonify, render_template, session, redirect, url_for, send_file, current_app
from models import db, AttendanceRecord, Payslip, AdvanceRequest
from sqlalchemy import func
from io import BytesIO

logger = logging.getLogger(__name__)

payslip_bp = Blueprint('payslip', __name__)


def _format_won(n):
    return f"{n:,}원"


# ── 관리자: 급여명세서 관리 페이지 ──────────────────────────
@payslip_bp.route('/admin/payslip')
def admin_payslip():
    if not session.get('is_admin'):
        return redirect(url_for('auth.login'))

    month = request.args.get('month', datetime.now().strftime('%Y-%m'))
    payslips = Payslip.query.filter(Payslip.month == month).order_by(Payslip.emp_name.asc()).all()

    cfg = current_app.config
    return render_template('admin_payslip.html',
                           payslips=payslips, month=month,
                           salary_mode=cfg.get('SALARY_MODE', 'standard'),
                           hourly_wage=cfg.get('HOURLY_WAGE', 10320))


# ── 관리자: 급여 일괄 생성 ─────────────────────────────────
@payslip_bp.route('/admin/payslip/generate', methods=['POST'])
def generate_payslips():
    if not session.get('is_admin'):
        return jsonify({'error': '권한이 없습니다.'}), 401

    month = request.form.get('month') or request.get_json(silent=True, force=True) and request.get_json().get('month')
    if not month:
        return jsonify({'error': 'month (YYYY-MM) required'}), 400

    salary_mode = request.form.get('salary_mode') or request.args.get('salary_mode')
    cfg = current_app.config
    if not salary_mode:
        salary_mode = cfg.get('SALARY_MODE', 'standard')

    hourly = cfg.get('HOURLY_WAGE', 10320)
    std_monthly_hours = cfg.get('MONTHLY_STANDARD_HOURS', 209)
    ot_mult = cfg.get('OT_MULTIPLIER', 1.5)
    night_prem = cfg.get('NIGHT_PREMIUM', 0.5)
    tax_rate = cfg.get('TAX_RATE', 0.033)
    ins_rate = cfg.get('INSURANCE_RATE', 0.097)

    # 해당 월 근태 기록 집계
    month_start = f"{month}-01"
    if int(month.split('-')[1]) == 12:
        next_y = int(month.split('-')[0]) + 1
        month_end = f"{next_y}-01-01"
    else:
        next_m = int(month.split('-')[1]) + 1
        month_end = f"{month.split('-')[0]}-{next_m:02d}-01"

    start_date = datetime.strptime(month_start, '%Y-%m-%d').date()
    end_date = datetime.strptime(month_end, '%Y-%m-%d').date()

    # 직원별 집계
    agg = db.session.query(
        AttendanceRecord.emp_id,
        AttendanceRecord.emp_name,
        AttendanceRecord.dept,
        func.sum(AttendanceRecord.total_work_hours).label('total_hours'),
        func.sum(AttendanceRecord.overtime_hours).label('ot_hours'),
        func.sum(AttendanceRecord.night_hours).label('night_hours'),
    ).filter(
        AttendanceRecord.work_date >= start_date,
        AttendanceRecord.work_date < end_date,
    ).group_by(
        AttendanceRecord.emp_id,
        AttendanceRecord.emp_name,
        AttendanceRecord.dept,
    ).all()

    if not agg:
        return jsonify({'error': f'{month} 근태 기록이 없습니다.'}), 404

    created = 0
    updated = 0
    try:
        for row in agg:
            emp_id, emp_name, dept = row.emp_id, row.emp_name, row.dept
            total_h = round(row.total_hours or 0, 2)
            ot_h = round(row.ot_hours or 0, 2)
            night_h = round(row.night_hours or 0, 2)

            # 기본급 계산
            if salary_mode == 'actual':
                base_salary = round(hourly * total_h)
            else:
                base_salary = hourly * std_monthly_hours

            # 잔업수당 = 잔업시간 × 시급 × OT배율
            ot_pay = round(ot_h * hourly * ot_mult)
            # 심야가산 = 심야시간 × 시급 × 심야가산배율 (추가 0.5배)
            night_pay = round(night_h * hourly * night_prem)

            gross = base_salary + ot_pay + night_pay
            tax = round(gross * tax_rate)
            insurance = round(gross * ins_rate)

            # 가불 차감 (approved 상태)
            adv_total = db.session.query(func.coalesce(func.sum(AdvanceRequest.amount), 0)).filter(
                AdvanceRequest.emp_id == emp_id,
                AdvanceRequest.request_month == month,
                AdvanceRequest.status == 'approved',
            ).scalar()

            net = gross - tax - insurance - adv_total

            # upsert
            existing = Payslip.query.filter_by(emp_id=emp_id, month=month).first()
            if existing:
                existing.salary_mode = salary_mode
                existing.total_work_hours = total_h
                existing.ot_hours = ot_h
                existing.night_hours = night_h
                existing.base_salary = base_salary
                existing.ot_pay = ot_pay
                existing.night_pay = night_pay
                existing.gross = gross
                existing.tax = tax
                existing.insurance = insurance
                existing.advance_deduction = adv_total
                existing.net = net
                updated += 1
            else:
                ps = Payslip(
                    emp_id=emp_id, emp_name=emp_name, dept=dept, month=month,
                    salary_mode=salary_mode,
                    total_work_hours=total_h, ot_hours=ot_h, night_hours=night_h,
                    base_salary=base_salary, ot_pay=ot_pay, night_pay=night_pay,
                    gross=gross, tax=tax, insurance=insurance,
                    advance_deduction=adv_total, net=net,
                )
                db.session.add(ps)
                created += 1

        db.session.commit()
        return jsonify({'success': True, 'created': created, 'updated': updated})
    except Exception as e:
        db.session.rollback()
        logger.error(f"Payslip generate error: {e}")
        return jsonify({'error': '급여 생성 중 오류가 발생했습니다.'}), 500


# ── 관리자: 급여 PDF ───────────────────────────────────────
@payslip_bp.route('/admin/payslip/pdf')
def payslip_pdf():
    if not session.get('is_admin'):
        return redirect(url_for('auth.login'))

    month = request.args.get('month', datetime.now().strftime('%Y-%m'))
    emp_id = request.args.get('emp_id')

    query = Payslip.query.filter(Payslip.month == month)
    if emp_id:
        query = query.filter(Payslip.emp_id == int(emp_id))
    payslips = query.order_by(Payslip.emp_name.asc()).all()

    if not payslips:
        return jsonify({'error': '해당 월 급여 데이터가 없습니다.'}), 404

    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    import os

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4

    # 한글 폰트 등록 시도
    font_name = 'Helvetica'
    for fp in [
        'C:/Windows/Fonts/malgun.ttf',
        'C:/Windows/Fonts/gulim.ttc',
        '/usr/share/fonts/truetype/nanum/NanumGothic.ttf',
    ]:
        if os.path.exists(fp):
            try:
                pdfmetrics.registerFont(TTFont('KoreanFont', fp))
                font_name = 'KoreanFont'
                break
            except Exception:
                continue

    cfg = current_app.config
    hourly = cfg.get('HOURLY_WAGE', 10320)

    for ps in payslips:
        y = h - 40 * mm

        # 헤더
        c.setFont(font_name, 16)
        c.drawString(30 * mm, y, 'HUMETIX Co., Ltd.')
        y -= 10 * mm
        c.setFont(font_name, 20)
        c.drawString(30 * mm, y, f'{ps.month} 급여명세서')
        y -= 12 * mm

        c.setFont(font_name, 11)
        c.drawString(30 * mm, y, f'성명: {ps.emp_name}    부서: {ps.dept}    시급: {hourly:,}원')
        y -= 8 * mm
        mode_label = '209h 고정' if ps.salary_mode == 'standard' else '실근무시간'
        c.drawString(30 * mm, y, f'산정방식: {mode_label}    총근무: {ps.total_work_hours}h')
        y -= 12 * mm

        # 지급 내역
        c.setFont(font_name, 12)
        c.drawString(30 * mm, y, '── 지급 내역 ──')
        y -= 8 * mm
        c.setFont(font_name, 11)
        items = [
            ('기본급', ps.base_salary),
            (f'잔업수당 ({ps.ot_hours}h × {hourly:,} × 1.5)', ps.ot_pay),
            (f'심야가산 ({ps.night_hours}h × {hourly:,} × 0.5)', ps.night_pay),
            ('총 지급액', ps.gross),
        ]
        for label, val in items:
            c.drawString(35 * mm, y, f'{label}')
            c.drawRightString(170 * mm, y, f'{val:,}원')
            y -= 7 * mm

        y -= 5 * mm
        c.setFont(font_name, 12)
        c.drawString(30 * mm, y, '── 공제 내역 ──')
        y -= 8 * mm
        c.setFont(font_name, 11)
        deductions = [
            ('소득세 (3.3%)', ps.tax),
            ('4대보험 (9.7%)', ps.insurance),
        ]
        if ps.advance_deduction > 0:
            deductions.append(('가불 차감', ps.advance_deduction))
        for label, val in deductions:
            c.drawString(35 * mm, y, f'{label}')
            c.drawRightString(170 * mm, y, f'-{val:,}원')
            y -= 7 * mm

        y -= 8 * mm
        c.setFont(font_name, 14)
        c.drawString(30 * mm, y, '실수령액')
        c.drawRightString(170 * mm, y, f'{ps.net:,}원')

        c.showPage()

    c.save()
    buf.seek(0)
    return send_file(buf, as_attachment=True,
                     download_name=f'급여명세서_{month}.pdf',
                     mimetype='application/pdf')


# ── 관리자: 급여 엑셀 ──────────────────────────────────────
@payslip_bp.route('/admin/payslip/excel')
def payslip_excel():
    if not session.get('is_admin'):
        return redirect(url_for('auth.login'))

    from openpyxl import Workbook
    from openpyxl.styles import Font

    month = request.args.get('month', datetime.now().strftime('%Y-%m'))
    payslips = Payslip.query.filter(Payslip.month == month).order_by(Payslip.emp_name.asc()).all()

    wb = Workbook()
    ws = wb.active
    ws.title = f'{month} 급여'

    headers = ['이름', '부서', '산정방식', '총근무(h)', '잔업(h)', '심야(h)',
               '기본급', '잔업수당', '심야가산', '총지급액', '소득세', '4대보험',
               '가불차감', '실수령액']
    bold = Font(bold=True)
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.font = bold

    for i, ps in enumerate(payslips, 2):
        mode_label = '209h고정' if ps.salary_mode == 'standard' else '실근무'
        vals = [ps.emp_name, ps.dept, mode_label,
                ps.total_work_hours, ps.ot_hours, ps.night_hours,
                ps.base_salary, ps.ot_pay, ps.night_pay,
                ps.gross, ps.tax, ps.insurance,
                ps.advance_deduction, ps.net]
        for col, v in enumerate(vals, 1):
            ws.cell(row=i, column=col, value=v)

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return send_file(buf, as_attachment=True,
                     download_name=f'급여명세서_{month}.xlsx',
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
