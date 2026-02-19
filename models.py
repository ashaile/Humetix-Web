import os
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Application(db.Model):
    """지원자 데이터 모델"""
    __tablename__ = 'applications'
    
    id = db.Column(db.String(36), primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.now, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now, index=True)
    photo = db.Column(db.String(200), default="")
    
    # 인적사항
    name = db.Column(db.String(50), nullable=False, index=True)
    birth = db.Column(db.Date)
    phone = db.Column(db.String(20), index=True)
    email = db.Column(db.String(100), index=True)
    gender = db.Column(db.String(10), index=True) # 성별 추가
    address = db.Column(db.String(200))
    
    # 신체정보
    height = db.Column(db.Integer)
    weight = db.Column(db.Integer)
    vision = db.Column(db.String(30))
    shoes = db.Column(db.Integer)
    tshirt = db.Column(db.String(10))
    
    # 근무조건
    shift = db.Column(db.String(10), index=True)
    posture = db.Column(db.String(10), index=True)
    overtime = db.Column(db.String(10), index=True)
    holiday = db.Column(db.String(10), index=True)
    interview_date = db.Column(db.Date)
    start_date = db.Column(db.Date)
    agree = db.Column(db.Boolean, default=False)
    
    # 기타 희망사항
    advance_pay = db.Column(db.String(10), default="???", index=True)
    insurance_type = db.Column(db.String(20), default="4대보험", index=True)
    memo = db.Column(db.Text, default="")  # 관리자용 메모
    status = db.Column(db.String(20), default="new", index=True)
    
    # 경력 관계
    careers = db.relationship('Career', backref='application', cascade='all, delete-orphan', lazy=True)
    
    def to_dict(self):
        """기존 JSON 형식과 동일한 딕셔너리 반환 (템플릿 호환)"""
        def _safe_str(val):
            return "" if val is None else str(val)

        return {
            "id": self.id,
            "timestamp": self.timestamp.strftime('%Y-%m-%d %H:%M:%S') if self.timestamp else "",
            "photo": self.photo,
            "memo": self.memo or "", # 메모 데이터 추가
            "status": self.status,
            "info": {
                "name": self.name,
                "birth": self.birth.strftime('%Y-%m-%d') if self.birth else "",
                "gender": self.gender,
                "phone": self.phone,
                "email": self.email,
                "address": self.address,
            },
            "career": [c.to_dict() for c in self.careers],
            "body": {
                "height": _safe_str(self.height),
                "weight": _safe_str(self.weight),
                "vision": self.vision or "",
                "shoes": _safe_str(self.shoes),
                "tshirt": self.tshirt or "",
            },
            "work_condition": {
                "shift": self.shift,
                "posture": self.posture,
                "overtime": self.overtime,
                "holiday": self.holiday,
                "interview_date": self.interview_date.strftime('%Y-%m-%d') if self.interview_date else "",
                "start_date": self.start_date.strftime('%Y-%m-%d') if self.start_date else "",
                "agree": "on" if self.agree else "off",
            },
            "extra": {
                "advance_pay": self.advance_pay,
                "insurance_type": self.insurance_type,
            }
        }


class Career(db.Model):
    """경력사항 모델"""
    __tablename__ = 'careers'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    application_id = db.Column(db.String(36), db.ForeignKey('applications.id'), nullable=False, index=True)
    company = db.Column(db.String(100))
    start = db.Column(db.Date)
    end = db.Column(db.Date)
    role = db.Column(db.String(100))
    reason = db.Column(db.String(200))
    
    def to_dict(self):
        return {
            "company": self.company,
            "start": self.start.strftime('%Y-%m-%d') if self.start else "",
            "end": self.end.strftime('%Y-%m-%d') if self.end else "",
            "role": self.role,
            "reason": self.reason,
        }


class Inquiry(db.Model):
    """견적 문의 폼 접수"""
    __tablename__ = 'inquiries'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    created_at = db.Column(db.DateTime, default=datetime.now, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now, index=True)
    company = db.Column(db.String(100), nullable=False, index=True)
    name = db.Column(db.String(50), nullable=False, index=True)
    phone = db.Column(db.String(30), nullable=False, index=True)
    email = db.Column(db.String(100), index=True)
    message = db.Column(db.Text)
    status = db.Column(db.String(20), default="new", index=True)
    assignee = db.Column(db.String(50))
    admin_memo = db.Column(db.Text)


class AttendanceRecord(db.Model):
    """출퇴근 기록 모델"""
    __tablename__ = 'attendance_records'
    __table_args__ = (
        db.Index('ix_attendance_emp_date', 'emp_name', 'work_date'),
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    emp_id = db.Column(db.Integer, nullable=True, index=True) # 사번 (선택사항으로 변경)
    birth_date = db.Column(db.String(8), nullable=True)         # 생년월일 (YYYYMMDD) - 식별용
    emp_name = db.Column(db.String(50), nullable=False)
    dept = db.Column(db.String(50), default='')
    work_date = db.Column(db.Date, nullable=False, index=True)
    clock_in = db.Column(db.String(5), nullable=True)           # "HH:MM" (결근/휴무 시 null 가능)
    clock_out = db.Column(db.String(5), nullable=True)          # "HH:MM"
    
    # work_type: normal(주간), night(야간), viral(연차), absent(결근), holiday(휴무), etc.
    work_type = db.Column(db.String(20), nullable=False, default='normal')
    
    total_work_hours = db.Column(db.Float, default=0.0)         # 총 근무시간
    overtime_hours = db.Column(db.Float, default=0.0)           # 잔업시간
    night_hours = db.Column(db.Float, default=0.0)              # 심야근무시간
    holiday_work_hours = db.Column(db.Float, default=0.0)       # 특근(주말/공휴일) 시간
    
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    def to_dict(self):
        return {
            'id': self.id,
            'emp_id': self.emp_id,
            'birth_date': self.birth_date,
            'emp_name': self.emp_name,
            'dept': self.dept,
            'work_date': self.work_date.strftime('%Y-%m-%d') if self.work_date else '',
            'clock_in': self.clock_in or '',
            'clock_out': self.clock_out or '',
            'work_type': self.work_type,
            'total_work_hours': self.total_work_hours,
            'overtime_hours': self.overtime_hours,
            'night_hours': self.night_hours,
            'holiday_work_hours': self.holiday_work_hours,
        }


class Payslip(db.Model):
    """급여명세서 모델"""
    __tablename__ = 'payslips'
    __table_args__ = (
        db.UniqueConstraint('emp_id', 'month', name='uq_payslip_emp_month'),
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    emp_id = db.Column(db.Integer, nullable=False, index=True)
    emp_name = db.Column(db.String(50), nullable=False)
    dept = db.Column(db.String(50), default='')
    month = db.Column(db.String(7), nullable=False, index=True)  # "YYYY-MM"
    salary_mode = db.Column(db.String(10), default='standard')   # standard | actual
    total_work_hours = db.Column(db.Float, default=0.0)
    ot_hours = db.Column(db.Float, default=0.0)
    night_hours = db.Column(db.Float, default=0.0)
    base_salary = db.Column(db.Integer, default=0)
    ot_pay = db.Column(db.Integer, default=0)
    night_pay = db.Column(db.Integer, default=0)
    gross = db.Column(db.Integer, default=0)
    tax = db.Column(db.Integer, default=0)
    insurance = db.Column(db.Integer, default=0)
    advance_deduction = db.Column(db.Integer, default=0)
    net = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    def to_dict(self):
        return {
            'id': self.id,
            'emp_id': self.emp_id,
            'emp_name': self.emp_name,
            'dept': self.dept,
            'month': self.month,
            'salary_mode': self.salary_mode,
            'total_work_hours': self.total_work_hours,
            'ot_hours': self.ot_hours,
            'night_hours': self.night_hours,
            'base_salary': self.base_salary,
            'ot_pay': self.ot_pay,
            'night_pay': self.night_pay,
            'gross': self.gross,
            'tax': self.tax,
            'insurance': self.insurance,
            'advance_deduction': self.advance_deduction,
            'net': self.net,
        }


class AdvanceRequest(db.Model):
    """가불 신청 모델"""
    __tablename__ = 'advance_requests'
    __table_args__ = (
        db.Index('ix_advance_emp_month', 'emp_id', 'request_month'),
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    emp_id = db.Column(db.Integer, nullable=True, index=True) # 사번 (선택사항)
    birth_date = db.Column(db.String(6), nullable=True)         # 생년월일 (YYMMDD)
    emp_name = db.Column(db.String(50), nullable=False)
    dept = db.Column(db.String(50), default='')
    request_month = db.Column(db.String(7), nullable=False, index=True)  # "YYYY-MM"
    work_type = db.Column(db.String(10), default='weekly')      # 'weekly' or 'shift'
    amount = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.Text, default='')
    status = db.Column(db.String(20), default='pending', index=True)
    # pending → approved/rejected, approved → paid/cancelled
    admin_comment = db.Column(db.Text, default='')
    created_at = db.Column(db.DateTime, default=datetime.now)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    def to_dict(self):
        return {
            'id': self.id,
            'emp_id': self.emp_id,
            'emp_name': self.emp_name,
            'dept': self.dept,
            'request_month': self.request_month,
            'amount': self.amount,
            'reason': self.reason,
            'status': self.status,
            'admin_comment': self.admin_comment,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else '',
            'reviewed_at': self.reviewed_at.strftime('%Y-%m-%d %H:%M') if self.reviewed_at else '',
        }


class Employee(db.Model):
    """직원 명부 모델 – 관리자가 미리 등록, 근태/가불 신청 시 검증용"""
    __tablename__ = 'employees'
    __table_args__ = (
        db.UniqueConstraint('name', 'birth_date', name='uq_employee_name_birth'),
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(50), nullable=False, index=True)
    birth_date = db.Column(db.String(6), nullable=False)         # YYMMDD
    work_type = db.Column(db.String(10), default='weekly')       # 'weekly' or 'shift'
    hire_date = db.Column(db.Date, nullable=True)                # 입사일
    resign_date = db.Column(db.Date, nullable=True)              # 퇴사일
    is_active = db.Column(db.Boolean, default=True)              # 재직 여부
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'birth_date': self.birth_date,
            'work_type': self.work_type,
            'hire_date': self.hire_date.strftime('%Y-%m-%d') if self.hire_date else '',
            'resign_date': self.resign_date.strftime('%Y-%m-%d') if self.resign_date else '',
            'is_active': self.is_active,
            'created_at': self.created_at.strftime('%Y-%m-%d') if self.created_at else '',
        }

