import os
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Application(db.Model):
    """지원자 데이터 모델"""
    __tablename__ = 'applications'
    
    id = db.Column(db.String(36), primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.now)
    photo = db.Column(db.String(200), default="")
    
    # 인적사항
    name = db.Column(db.String(50), nullable=False)
    birth = db.Column(db.Date)
    phone = db.Column(db.String(20))
    email = db.Column(db.String(100))
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
    memo = db.Column(db.Text, default="")  # 관리자용 메모 추가
    
    # 경력 관계
    careers = db.relationship('Career', backref='application', cascade='all, delete-orphan', lazy=True)
    
    def to_dict(self):
        """기존 JSON 형식과 동일한 딕셔너리 반환 (템플릿 호환)"""
        return {
            "id": self.id,
            "timestamp": self.timestamp.strftime('%Y-%m-%d %H:%M:%S') if self.timestamp else "",
            "photo": self.photo,
            "memo": self.memo or "", # 메모 데이터 추가
            "info": {
                "name": self.name,
                "birth": self.birth.strftime('%Y-%m-%d') if self.birth else "",
                "phone": self.phone,
                "email": self.email,
                "address": self.address,
            },
            "career": [c.to_dict() for c in self.careers],
            "body": {
                "height": str(self.height),
                "weight": str(self.weight),
                "vision": self.vision,
                "shoes": str(self.shoes),
                "tshirt": self.tshirt,
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
