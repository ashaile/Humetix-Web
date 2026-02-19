import logging
from datetime import datetime
from flask import Blueprint, request, jsonify, render_template, session, redirect, url_for, current_app
from models import db, AdvanceRequest, Employee

logger = logging.getLogger(__name__)

advance_bp = Blueprint('advance', __name__)


# ── 직원: 가불 신청 페이지 + 제출 ──────────────────────────
@advance_bp.route('/advance', methods=['GET', 'POST'])
def advance_page():
    cfg = current_app.config
    limit_weekly = cfg.get('ADVANCE_LIMIT_WEEKLY', 300000)
    limit_shift = cfg.get('ADVANCE_LIMIT_SHIFT', 500000)

    if request.method == 'GET':
        return render_template('advance.html', limit_weekly=limit_weekly, limit_shift=limit_shift)

    # POST: 신청 접수
    birth_date = request.form.get('birth_date', '').strip()
    emp_name = request.form.get('emp_name', '').strip()
    # dept = request.form.get('dept', '').strip() # Removed
    dept = '' # Optional
    work_type = request.form.get('work_type', 'weekly')
    request_month = request.form.get('request_month', '').strip()
    amount_str = request.form.get('amount', '').strip()
    reason = request.form.get('reason', '').strip()

    errors = []
    if not birth_date or len(birth_date) != 6 or not birth_date.isdigit():
        errors.append('생년월일 6자리를 정확히 입력하세요.')
    if not emp_name:
        errors.append('이름을 입력하세요.')

    # 직원 명부 검증
    registered = None
    if birth_date and emp_name and not errors:
        registered = Employee.query.filter_by(name=emp_name, birth_date=birth_date, is_active=True).first()
        if not registered:
            errors.append('등록되지 않은 직원입니다. 관리자에게 문의하세요.')
        else:
            # 명부의 근무형태를 자동 적용
            work_type = registered.work_type
    if not request_month:
        errors.append('신청 월을 선택하세요.')
    if not amount_str:
        errors.append('금액을 입력하세요.')

    try:
        amount = int(amount_str) if amount_str else 0
    except ValueError:
        errors.append('금액은 숫자여야 합니다.')
        amount = 0

    if amount <= 0 and not errors:
        errors.append('금액은 0보다 커야 합니다.')

    # 한도 검증
    limit = limit_shift if work_type == 'shift' else limit_weekly
    if amount > limit:
        errors.append(f'선택하신 근무 형태의 가불 한도({limit:,}원)를 초과했습니다.')

    # 동일 birth_date + month에 pending/approved 중복 방지
    if birth_date and request_month:
        dup = AdvanceRequest.query.filter(
            AdvanceRequest.birth_date == birth_date,
            AdvanceRequest.request_month == request_month,
            AdvanceRequest.status.in_(['pending', 'approved']),
        ).first()
        if dup:
            errors.append(f'{request_month} 해당 월에 이미 신청/승인된 가불이 있습니다.')

    if errors:
        return render_template('advance.html',
                               errors=errors, limit_weekly=limit_weekly, limit_shift=limit_shift,
                               form=request.form)

    try:
        adv = AdvanceRequest(
            birth_date=birth_date,
            emp_name=emp_name,
            dept=dept,
            work_type=work_type,
            request_month=request_month,
            amount=amount,
            reason=reason,
        )
        db.session.add(adv)
        db.session.commit()
        return render_template('advance.html',
                               success=True, limit_weekly=limit_weekly, limit_shift=limit_shift)
    except Exception as e:
        db.session.rollback()
        logger.error(f"Advance create error: {e}")
        return render_template('advance.html',
                               errors=['서버 오류가 발생했습니다.'],
                               limit_weekly=limit_weekly, limit_shift=limit_shift, form=request.form)


# ── 관리자: 가불 목록 ─────────────────────────────────────
@advance_bp.route('/admin/advance')
def admin_advance():
    if not session.get('is_admin'):
        return redirect(url_for('auth.login'))

    month = request.args.get('month', '')
    status = request.args.get('status', '')

    query = AdvanceRequest.query
    if month:
        query = query.filter(AdvanceRequest.request_month == month)
    if status:
        query = query.filter(AdvanceRequest.status == status)

    items = query.order_by(AdvanceRequest.created_at.desc()).all()
    return render_template('admin_advance.html',
                           items=items, month=month, filter_status=status)


# ── 관리자: 승인 ──────────────────────────────────────────
@advance_bp.route('/admin/advance/<int:adv_id>/approve', methods=['POST'])
def approve_advance(adv_id):
    if not session.get('is_admin'):
        return jsonify({'error': '권한이 없습니다.'}), 401

    try:
        adv = AdvanceRequest.query.get(adv_id)
        if not adv:
            return jsonify({'error': '가불 신청을 찾을 수 없습니다.'}), 404

        if adv.status != 'pending':
            return jsonify({'error': f'현재 상태({adv.status})에서는 승인할 수 없습니다.'}), 400

        adv.status = 'approved'
        adv.admin_comment = request.form.get('comment', '')
        adv.reviewed_at = datetime.now()
        db.session.commit()
        return jsonify({'success': True, 'status': 'approved'})
    except Exception as e:
        db.session.rollback()
        logger.error(f"Advance approve error: {e}")
        return jsonify({'error': '처리 중 오류가 발생했습니다.'}), 500


# ── 관리자: 반려 ──────────────────────────────────────────
@advance_bp.route('/admin/advance/<int:adv_id>/reject', methods=['POST'])
def reject_advance(adv_id):
    if not session.get('is_admin'):
        return jsonify({'error': '권한이 없습니다.'}), 401

    try:
        adv = AdvanceRequest.query.get(adv_id)
        if not adv:
            return jsonify({'error': '가불 신청을 찾을 수 없습니다.'}), 404

        if adv.status != 'pending':
            return jsonify({'error': f'현재 상태({adv.status})에서는 반려할 수 없습니다.'}), 400

        adv.status = 'rejected'
        adv.admin_comment = request.form.get('comment', '')
        adv.reviewed_at = datetime.now()
        db.session.commit()
        return jsonify({'success': True, 'status': 'rejected'})
    except Exception as e:
        db.session.rollback()
        logger.error(f"Advance reject error: {e}")
        return jsonify({'error': '처리 중 오류가 발생했습니다.'}), 500
