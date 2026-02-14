import os
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Application(db.Model):
    """지원자 데이터 모델"""
    __tablename__ = 'applications'
    
    id = db.Column(db.String(36), primary_key=True)
    timestamp = db.Column(db.String(20), nullable=False)
    photo = db.Column(db.String(200), default="")
    
    # 인적사항
    name = db.Column(db.String(50), nullable=False)
    birth = db.Column(db.String(20))
    phone = db.Column(db.String(20))
    email = db.Column(db.String(100))
    address = db.Column(db.String(200))
    
    # 신체정보
    height = db.Column(db.String(10))
    weight = db.Column(db.String(10))
    vision = db.Column(db.String(30))
    shoes = db.Column(db.String(10))
    tshirt = db.Column(db.String(10))
    
    # 근무조건
    shift = db.Column(db.String(10))
    posture = db.Column(db.String(10))
    overtime = db.Column(db.String(10))
    holiday = db.Column(db.String(10))
    interview_date = db.Column(db.String(20))
    start_date = db.Column(db.String(20))
    agree = db.Column(db.String(10))
    
    # 기타 희망사항
    advance_pay = db.Column(db.String(10), default="")
    insurance_type = db.Column(db.String(20), default="4대보험")
    
    # 경력 관계
    careers = db.relationship('Career', backref='application', cascade='all, delete-orphan', lazy=True)
    
    def to_dict(self):
        """기존 JSON 형식과 동일한 딕셔너리 반환 (템플릿 호환)"""
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "photo": self.photo,
            "info": {
                "name": self.name,
                "birth": self.birth,
                "phone": self.phone,
                "email": self.email,
                "address": self.address,
            },
            "career": [c.to_dict() for c in self.careers],
            "body": {
                "height": self.height,
                "weight": self.weight,
                "vision": self.vision,
                "shoes": self.shoes,
                "tshirt": self.tshirt,
            },
            "work_condition": {
                "shift": self.shift,
                "posture": self.posture,
                "overtime": self.overtime,
                "holiday": self.holiday,
                "interview_date": self.interview_date,
                "start_date": self.start_date,
                "agree": self.agree,
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
    start = db.Column(db.String(20))
    end = db.Column(db.String(20))
    role = db.Column(db.String(100))
    reason = db.Column(db.String(200))
    
    def to_dict(self):
        return {
            "company": self.company,
            "start": self.start,
            "end": self.end,
            "role": self.role,
            "reason": self.reason,
        }
