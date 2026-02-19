import logging
from datetime import datetime
from flask import Blueprint, request, jsonify, render_template, session, redirect, url_for
from models import db, Employee

logger = logging.getLogger(__name__)

employee_bp = Blueprint('employee', __name__)


# ── 관리자: 직원 명부 관리 페이지 ─────────────────────────
@employee_bp.route('/admin/employees')
def admin_employees():
    if not session.get('is_admin'):
        return redirect(url_for('auth.login'))

    employees = Employee.query.order_by(Employee.name).all()
    return render_template('admin_employee.html', employees=employees)


# ── API: 직원 등록 ────────────────────────────────────────
@employee_bp.route('/api/employees', methods=['POST'])
def create_employee():
    if not session.get('is_admin'):
        return jsonify({'error': '권한이 없습니다.'}), 401

    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'JSON body required'}), 400

    name = data.get('name', '').strip()
    birth_date = data.get('birth_date', '').strip()
    hire_date_str = data.get('hire_date', '').strip()

    if not name:
        return jsonify({'error': '이름을 입력하세요.'}), 400
    if not birth_date or len(birth_date) != 6 or not birth_date.isdigit():
        return jsonify({'error': '생년월일 6자리(YYMMDD)를 입력하세요.'}), 400

    # 입사일 파싱
    hire_date = None
    if hire_date_str:
        try:
            hire_date = datetime.strptime(hire_date_str, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'error': '입사일 형식이 올바르지 않습니다 (YYYY-MM-DD).'}), 400

    # 중복 검사
    existing = Employee.query.filter_by(name=name, birth_date=birth_date).first()
    if existing:
        return jsonify({'error': f'{name}({birth_date}) 직원이 이미 등록되어 있습니다.'}), 400

    try:
        emp = Employee(name=name, birth_date=birth_date, hire_date=hire_date)
        db.session.add(emp)
        db.session.commit()
        return jsonify({'success': True, 'employee': emp.to_dict()}), 201
    except Exception as e:
        db.session.rollback()
        logger.error(f"Employee create error: {e}")
        return jsonify({'error': '서버 오류가 발생했습니다.'}), 500


# ── API: 직원 수정 ────────────────────────────────────────
@employee_bp.route('/api/employees/<int:emp_id>', methods=['PUT'])
def update_employee(emp_id):
    if not session.get('is_admin'):
        return jsonify({'error': '권한이 없습니다.'}), 401

    emp = Employee.query.get(emp_id)
    if not emp:
        return jsonify({'error': '직원을 찾을 수 없습니다.'}), 404

    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'JSON body required'}), 400

    try:
        if 'name' in data:
            emp.name = data['name'].strip()
        if 'birth_date' in data:
            bd = data['birth_date'].strip()
            if len(bd) != 6 or not bd.isdigit():
                return jsonify({'error': '생년월일 6자리(YYMMDD)를 입력하세요.'}), 400
            emp.birth_date = bd
        if 'work_type' in data:
            emp.work_type = data['work_type']
        if 'is_active' in data:
            emp.is_active = bool(data['is_active'])
        if 'hire_date' in data:
            hd = data['hire_date'].strip() if data['hire_date'] else ''
            emp.hire_date = datetime.strptime(hd, '%Y-%m-%d').date() if hd else None
        if 'resign_date' in data:
            rd = data['resign_date'].strip() if data['resign_date'] else ''
            emp.resign_date = datetime.strptime(rd, '%Y-%m-%d').date() if rd else None

        db.session.commit()
        return jsonify({'success': True, 'employee': emp.to_dict()})
    except Exception as e:
        db.session.rollback()
        logger.error(f"Employee update error: {e}")
        return jsonify({'error': '서버 오류가 발생했습니다.'}), 500


# ── API: 직원 삭제 ────────────────────────────────────────
@employee_bp.route('/api/employees/<int:emp_id>', methods=['DELETE'])
def delete_employee(emp_id):
    if not session.get('is_admin'):
        return jsonify({'error': '권한이 없습니다.'}), 401

    emp = Employee.query.get(emp_id)
    if not emp:
        return jsonify({'error': '직원을 찾을 수 없습니다.'}), 404

    try:
        db.session.delete(emp)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        logger.error(f"Employee delete error: {e}")
        return jsonify({'error': '서버 오류가 발생했습니다.'}), 500


# ── API: 직원 검증 (근태/가불 신청 시 호출) ────────────────
@employee_bp.route('/api/employees/verify', methods=['POST'])
def verify_employee():
    """이름 + 생년월일로 직원 명부에 등록 여부 확인"""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'JSON body required'}), 400

    name = data.get('name', '').strip()
    birth_date = data.get('birth_date', '').strip()

    if not name or not birth_date:
        return jsonify({'verified': False, 'error': '이름과 생년월일을 입력하세요.'}), 400

    emp = Employee.query.filter_by(name=name, birth_date=birth_date, is_active=True).first()
    if emp:
        return jsonify({'verified': True, 'employee': emp.to_dict()})
    else:
        return jsonify({'verified': False, 'error': '등록되지 않은 직원입니다. 관리자에게 문의하세요.'})
