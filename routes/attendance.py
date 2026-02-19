import logging
from datetime import datetime, date
from flask import Blueprint, request, jsonify, render_template, session, redirect, url_for, send_file, current_app
from models import db, AttendanceRecord, Employee
from io import BytesIO

logger = logging.getLogger(__name__)

attendance_bp = Blueprint('attendance', __name__)


# ── 근무시간 계산 유틸리티 ──────────────────────────────────
def _time_to_minutes(hhmm: str) -> int:
    """'HH:MM' → 분(int)"""
    h, m = map(int, hhmm.split(':'))
    return h * 60 + m


def _minutes_in_range(start_min, end_min, range_start_min, range_end_min):
    """start~end 구간 중 range_start~range_end 구간에 겹치는 분 수 계산.
    야간(22:00~06:00)처럼 range가 자정을 넘는 경우도 처리."""
    if range_start_min >= range_end_min:
        # 자정을 넘는 구간 (예: 22:00 ~ 06:00 → 22:00~24:00 + 00:00~06:00)
        part1 = _minutes_in_range(start_min, end_min, range_start_min, 24 * 60)
        part2 = _minutes_in_range(start_min, end_min, 0, range_end_min)
        return part1 + part2

    overlap_start = max(start_min, range_start_min)
    overlap_end = min(end_min, range_end_min)
    return max(0, overlap_end - overlap_start)


def calc_work_hours(clock_in: str, clock_out: str, work_type: str, cfg, work_date=None):
    """출퇴근 시간 → (총근무시간, 잔업시간, 심야시간, 특근시간) 튜플 반환.
    휴게시간(BREAK_HOURS) 차감, 야간(clock_out < clock_in) 자동 감지.
    work_date: datetime.date 객체 (주말/공휴일 특근 판단용)
    """
    in_min = _time_to_minutes(clock_in)
    out_min = _time_to_minutes(clock_out)

    # 야간근무: clock_out < clock_in → 다음날로 취급
    if out_min <= in_min:
        raw_minutes = (24 * 60 - in_min) + out_min
    else:
        raw_minutes = out_min - in_min

    break_min = int(cfg.get('BREAK_HOURS', 1.0) * 60)
    worked_min = max(0, raw_minutes - break_min)
    total_hours = round(worked_min / 60, 2)

    # 특근(Special Work) 판단: 토(5), 일(6) 또는 공휴일
    is_holiday_work = False
    if work_date:
        # work_date가 문자열이면 변환
        if isinstance(work_date, str):
            try:
                work_date = datetime.strptime(work_date, '%Y-%m-%d').date()
            except:
                pass
        
        # 1. 주말 체크
        if work_date.weekday() >= 5: # 5=Sat, 6=Sun
            is_holiday_work = True
        
        # 2. 공휴일 체크 (Config 리스트)
        holidays_2026 = cfg.get('PUBLIC_HOLIDAYS_2026', [])
        iso_date = work_date.strftime('%Y-%m-%d')
        if iso_date in holidays_2026:
            is_holiday_work = True

    std_hours = cfg.get('STANDARD_WORK_HOURS', 8.0)
    
    if is_holiday_work:
        # 특근: 전체 근무시간이 특근 시간으로 인정 (1.5배) - 잔업 0 처리
        ot_hours = 0.0
        holiday_work_hours = total_hours
    else:
        # 평일: 8시간 초과분 잔업
        ot_hours = round(max(0, total_hours - std_hours), 2)
        holiday_work_hours = 0.0

    # 심야 시간 계산 (22:00 ~ 06:00 구간)
    night_start = cfg.get('NIGHT_START', 22) * 60
    night_end = cfg.get('NIGHT_END', 6) * 60

    if out_min <= in_min:
        # 자정 넘는 근무: in~24:00 + 0:00~out
        night_min1 = _minutes_in_range(in_min, 24 * 60, night_start, 24 * 60)
        night_min2 = _minutes_in_range(0, out_min, 0, night_end)
        night_total = night_min1 + night_min2
    else:
        night_total = _minutes_in_range(in_min, out_min, night_start, night_end)

    # 심야 시간: 휴게시간(1시간) 차감 (사용자 요청)
    night_calc = max(0, night_total - break_min)
    night_hours = round(night_calc / 60, 2)

    return total_hours, ot_hours, night_hours, holiday_work_hours


def _get_cfg():
    """현재 앱 config에서 급여 관련 값을 dict로 반환"""
    c = current_app.config
    return {
        'STANDARD_WORK_HOURS': c.get('STANDARD_WORK_HOURS', 8.0),
        'BREAK_HOURS': c.get('BREAK_HOURS', 1.0),
        'NIGHT_START': c.get('NIGHT_START', 22),
        'NIGHT_END': c.get('NIGHT_END', 6),
        'PUBLIC_HOLIDAYS_2026': c.get('PUBLIC_HOLIDAYS_2026', []),
    }


# ── API: 출퇴근 기록 생성 ──────────────────────────────────
# ── API: 출퇴근 기록 생성 ──────────────────────────────────
@attendance_bp.route('/api/attendance', methods=['POST'])
def create_attendance():
    """POST /api/attendance - 출퇴근 기록 생성 (생년월일 식별)"""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'JSON body required'}), 400

    # 필수 필드 변경: emp_id 제거, birth_date 추가
    required = ['emp_name', 'birth_date', 'work_date']
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({'error': f'Missing fields: {", ".join(missing)}'}), 400

    # 생년월일 검증 (YYMMDD)
    birth_date = data['birth_date'].strip()
    if not birth_date.isdigit() or len(birth_date) != 6:
        return jsonify({'error': '생년월일은 6자리 숫자(YYMMDD)여야 합니다.'}), 400

    # 직원 명부 검증
    emp_name = data['emp_name'].strip()
    registered = Employee.query.filter_by(name=emp_name, birth_date=birth_date, is_active=True).first()
    if not registered:
        return jsonify({'error': '등록되지 않은 직원입니다. 관리자에게 문의하세요.'}), 403

    try:
        work_date = datetime.strptime(data['work_date'], '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'error': 'work_date format: YYYY-MM-DD'}), 400

    work_type = data.get('work_type', 'normal')
    allowed_types = ('normal', 'night', 'annual', 'absent', 'holiday', 'early')
    if work_type not in allowed_types:
        return jsonify({'error': f'Invalid work_type: {work_type}'}), 400

    # 특수 근무 유형 처리 (시간 계산 없음)
    clock_in = data.get('clock_in', '').strip()
    clock_out = data.get('clock_out', '').strip()
    
    total_hours = 0.0
    ot_hours = 0.0
    night_hours = 0.0
    holiday_hours = 0.0

    # 정상/야간 근무일 때만 시간 계산 수행
    if work_type in ('normal', 'night'):
        if not clock_in or not clock_out:
             return jsonify({'error': '출퇴근 시간을 입력해주세요.'}), 400

        for t in [clock_in, clock_out]:
            if len(t) != 5 or t[2] != ':':
                return jsonify({'error': f'Time format must be HH:MM, got: {t}'}), 400
            try:
                int(t[:2])
                int(t[3:])
            except ValueError:
                return jsonify({'error': f'Invalid time: {t}'}), 400
        
        cfg = _get_cfg()
        total_hours, ot_hours, night_hours, holiday_hours = calc_work_hours(clock_in, clock_out, work_type, cfg, work_date=work_date)

    # 사번(emp_id)은 이제 선택사항이므로 0 또는 None 처리, 혹은 기존 로직 유지를 위해 임시 값 할당
    # 여기서는 입력받지 않으므로 None으로 저장 (모델에서 nullable=True)
    emp_id = None 

    try:
        rec = AttendanceRecord(
            emp_id=emp_id,
            birth_date=birth_date,
            emp_name=data['emp_name'].strip(),
            dept=data.get('dept', '').strip(),
            work_date=work_date,
            clock_in=clock_in,
            clock_out=clock_out,
            work_type=work_type,
            total_work_hours=total_hours,
            overtime_hours=ot_hours,
            night_hours=night_hours,
            holiday_work_hours=holiday_hours,
        )
        db.session.add(rec)
        db.session.commit()
        return jsonify({'success': True, 'record': rec.to_dict()}), 201
    except Exception as e:
        db.session.rollback()
        logger.error(f"Attendance create error: {e}")
        return jsonify({'error': '서버 오류가 발생했습니다.'}), 500


# ── API: 근태 기록 조회 ────────────────────────────────────
@attendance_bp.route('/api/attendance', methods=['GET'])
def list_attendance():
    """GET /api/attendance - 기간/직원 필터, work_date ASC"""
    query = AttendanceRecord.query

    emp_id = request.args.get('emp_id')
    if emp_id:
        query = query.filter(AttendanceRecord.emp_id == int(emp_id))

    start = request.args.get('start_date')
    if start:
        query = query.filter(AttendanceRecord.work_date >= datetime.strptime(start, '%Y-%m-%d').date())
    end = request.args.get('end_date')
    if end:
        query = query.filter(AttendanceRecord.work_date <= datetime.strptime(end, '%Y-%m-%d').date())

    records = query.order_by(AttendanceRecord.work_date.asc()).all()
    return jsonify({'records': [r.to_dict() for r in records]})


# ── 직원용: 근무 입력 페이지 ───────────────────────────────
@attendance_bp.route('/attendance')
def attendance_page():
    """근무 입력 + 대시보드 (직원/관리자 공용)"""
    today = date.today()
    today_records = AttendanceRecord.query.filter(
        AttendanceRecord.work_date == today
    ).order_by(AttendanceRecord.emp_name.asc()).all()

    # 대시보드 제거 (관리자 페이지로 이동)
    return render_template('attendance.html', records=today_records, today=today)


# ── 관리자: 근태 관리 페이지 ───────────────────────────────
@attendance_bp.route('/admin/attendance')
def admin_attendance():
    if not session.get('is_admin'):
        return redirect(url_for('auth.login'))

    start = request.args.get('start_date', '')
    end = request.args.get('end_date', '')
    emp_name = request.args.get('emp_name', '')

    query = AttendanceRecord.query
    if start:
        query = query.filter(AttendanceRecord.work_date >= datetime.strptime(start, '%Y-%m-%d').date())
    if end:
        query = query.filter(AttendanceRecord.work_date <= datetime.strptime(end, '%Y-%m-%d').date())
    if emp_name:
        query = query.filter(AttendanceRecord.emp_name.contains(emp_name))

    records = query.order_by(AttendanceRecord.work_date.desc()).all()

    # 대시보드 통계 (오늘 기준 전체 현황 + 특근)
    today = date.today()
    today_recs = AttendanceRecord.query.filter(AttendanceRecord.work_date == today).all()
    stats = {
        'total': len(today_recs),
        'day': len([r for r in today_recs if r.work_type == 'normal']),
        'night': len([r for r in today_recs if r.work_type == 'night']),
        'total_work': round(sum(r.total_work_hours for r in today_recs), 1),
        'total_night': round(sum(r.night_hours for r in today_recs), 1),
        'total_ot': round(sum(r.overtime_hours for r in today_recs), 1),
        'total_holiday': round(sum((r.holiday_work_hours or 0) for r in today_recs), 1),
    }

    return render_template('admin_attendance.html',
                           records=records, start_date=start, end_date=end, emp_name=emp_name,
                           stats=stats, today=today)


# ── 관리자: 근태 엑셀 다운로드 ─────────────────────────────
@attendance_bp.route('/admin/attendance/excel')
def attendance_excel():
    if not session.get('is_admin'):
        return redirect(url_for('auth.login'))

    from openpyxl import Workbook
    from openpyxl.styles import Font

    start = request.args.get('start_date', '')
    end = request.args.get('end_date', '')
    emp_name = request.args.get('emp_name', '')

    query = AttendanceRecord.query
    if start:
        query = query.filter(AttendanceRecord.work_date >= datetime.strptime(start, '%Y-%m-%d').date())
    if end:
        query = query.filter(AttendanceRecord.work_date <= datetime.strptime(end, '%Y-%m-%d').date())
    if emp_name:
        query = query.filter(AttendanceRecord.emp_name.contains(emp_name))

    records = query.order_by(AttendanceRecord.work_date.asc()).all()

    wb = Workbook()
    ws = wb.active
    ws.title = '근태기록'

    headers = ['이름', '부서', '날짜', '출근', '퇴근', '구분', '총근무(h)', '잔업(h)', '심야(h)', '특근(h)']
    bold = Font(bold=True)
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.font = bold

    for i, r in enumerate(records, 2):
        ws.cell(row=i, column=1, value=r.emp_name)
        ws.cell(row=i, column=2, value=r.dept)
        ws.cell(row=i, column=3, value=r.work_date.strftime('%Y-%m-%d') if r.work_date else '')
        ws.cell(row=i, column=4, value=r.clock_in)
        ws.cell(row=i, column=5, value=r.clock_out)
        ws.cell(row=i, column=6, value='주간' if r.work_type == 'normal' else '야간')
        ws.cell(row=i, column=7, value=r.total_work_hours)
        ws.cell(row=i, column=8, value=r.overtime_hours)
        ws.cell(row=i, column=9, value=r.night_hours)
        ws.cell(row=i, column=10, value=r.holiday_work_hours or 0)

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return send_file(buf, as_attachment=True,
                     download_name=f'근태기록_{start or "all"}_{end or "all"}.xlsx',
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

# ── API: 근태 기록 수정 ────────────────────────────────────
@attendance_bp.route('/api/attendance/<int:record_id>', methods=['PUT', 'POST'])
def update_attendance(record_id):
    """PUT/POST /api/attendance/<id> - 근태 기록 수정 (관리자용)"""
    if not session.get('is_admin'):
        return jsonify({'error': 'Unauthorized'}), 403

    rec = AttendanceRecord.query.get_or_404(record_id)
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'JSON body required'}), 400

    # 필드 업데이트
    if 'emp_name' in data:
        rec.emp_name = data['emp_name']
    if 'dept' in data:
        rec.dept = data['dept']
    if 'work_date' in data:
        try:
            rec.work_date = datetime.strptime(data['work_date'], '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'error': 'Invalid date format'}), 400
    
    # 시간/유형 변경 시 재계산
    needs_recalc = False
    if 'clock_in' in data:
        rec.clock_in = data['clock_in']
        needs_recalc = True
    if 'clock_out' in data:
        rec.clock_out = data['clock_out']
        needs_recalc = True
    if 'work_type' in data:
        rec.work_type = data['work_type']
        needs_recalc = True

    if needs_recalc:
        cfg = _get_cfg()
        # work_date는 기존 rec.work_date 또는 업데이트된 값 사용
        target_date = rec.work_date
        if 'work_date' in data: # 위에서 이미 처리했으나 확인용
             target_date = rec.work_date

        total, ot, night, holiday = calc_work_hours(rec.clock_in, rec.clock_out, rec.work_type, cfg, work_date=target_date)
        rec.total_work_hours = total
        rec.overtime_hours = ot
        rec.night_hours = night
        rec.holiday_work_hours = holiday

    try:
        db.session.commit()
        return jsonify({'success': True, 'record': rec.to_dict()})
    except Exception as e:
        db.session.rollback()
        logger.error(f"Update error: {e}")
        return jsonify({'error': str(e)}), 500


# ── API: 근태 기록 삭제 ────────────────────────────────────
@attendance_bp.route('/api/attendance/<int:record_id>', methods=['DELETE'])
def delete_attendance(record_id):
    """DELETE /api/attendance/<id> - 근태 기록 삭제 (관리자용)"""
    if not session.get('is_admin'):
        return jsonify({'error': 'Unauthorized'}), 403

    rec = AttendanceRecord.query.get_or_404(record_id)
    try:
        db.session.delete(rec)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'DELETE Failed'}), 500
