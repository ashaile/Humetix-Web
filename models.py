from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

# 상태 상수
APPLICATION_STATUSES = ['접수', '서류심사', '면접예정', '합격', '불합격', '보류']


class Application(db.Model):
    """지원자 데이터 모델"""
    __tablename__ = 'applications'

    id = db.Column(db.String(36), primary_key=True)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    photo = db.Column(db.String(200), default="")
    status = db.Column(db.String(20), default="접수", index=True)

    # 인적사항
    name = db.Column(db.String(50), nullable=False, index=True)
    birth = db.Column(db.Date)
    phone = db.Column(db.String(20), index=True)
    email = db.Column(db.String(100))
    gender = db.Column(db.String(10))
    address = db.Column(db.String(200))

    # 신체정보
    height = db.Column(db.Integer)
    weight = db.Column(db.Integer)
    vision = db.Column(db.String(30))
    shoes = db.Column(db.Integer)
    tshirt = db.Column(db.String(10))

    # 근무조건
    shift = db.Column(db.String(10))
    posture = db.Column(db.String(10))
    overtime = db.Column(db.String(10))
    holiday = db.Column(db.String(10))
    interview_date = db.Column(db.Date)
    start_date = db.Column(db.Date)
    agree = db.Column(db.Boolean, default=False)

    # 기타 희망사항
    advance_pay = db.Column(db.String(10), default="")
    insurance_type = db.Column(db.String(20), default="4대보험")
    memo = db.Column(db.Text, default="")

    # 경력 관계
    careers = db.relationship('Career', backref='application', cascade='all, delete-orphan', lazy=True)

    # 상태 표시용 속성
    STATUS_COLORS = {
        '접수': '#6c757d',
        '서류심사': '#0d6efd',
        '면접예정': '#fd7e14',
        '합격': '#198754',
        '불합격': '#dc3545',
        '보류': '#ffc107',
    }

    @property
    def status_color(self):
        return self.STATUS_COLORS.get(self.status, '#6c757d')

    @property
    def status_display(self):
        return self.status or '접수'

    def to_dict(self):
        """기존 JSON 형식과 동일한 딕셔너리 반환 (템플릿 호환)"""
        return {
            "id": self.id,
            "timestamp": self.timestamp.strftime('%Y-%m-%d %H:%M:%S') if self.timestamp else "",
            "photo": self.photo,
            "memo": self.memo or "",
            "status": self.status or "접수",
            "status_display": self.status_display,
            "status_color": self.status_color,
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
                "height": str(self.height) if self.height else "",
                "weight": str(self.weight) if self.weight else "",
                "vision": self.vision or "",
                "shoes": str(self.shoes) if self.shoes else "",
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
    application_id = db.Column(db.String(36), db.ForeignKey('applications.id'), nullable=False)
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
