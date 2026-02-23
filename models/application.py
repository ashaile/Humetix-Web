from datetime import datetime

from models._base import db


class Application(db.Model):
    __tablename__ = "applications"

    id = db.Column(db.String(36), primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.now, index=True)
    updated_at = db.Column(
        db.DateTime, default=datetime.now, onupdate=datetime.now, index=True
    )
    photo = db.Column(db.String(200), default="")

    name = db.Column(db.String(50), nullable=False, index=True)
    birth = db.Column(db.Date)
    phone = db.Column(db.String(20), index=True)
    email = db.Column(db.String(100), index=True)
    gender = db.Column(db.String(10), index=True)
    address = db.Column(db.String(200))

    height = db.Column(db.Integer)
    weight = db.Column(db.Integer)
    vision = db.Column(db.String(30))
    shoes = db.Column(db.Integer)
    tshirt = db.Column(db.String(10))

    shift = db.Column(db.String(10), index=True)
    posture = db.Column(db.String(10), index=True)
    overtime = db.Column(db.String(10), index=True)
    holiday = db.Column(db.String(10), index=True)
    interview_date = db.Column(db.Date)
    start_date = db.Column(db.Date)
    agree = db.Column(db.Boolean, default=False)

    advance_pay = db.Column(db.String(10), default="비희망", index=True)
    insurance_type = db.Column(db.String(20), default="4대보험", index=True)
    memo = db.Column(db.Text, default="")
    status = db.Column(db.String(20), default="new", index=True)

    careers = db.relationship(
        "Career", backref="application", cascade="all, delete-orphan", lazy=True
    )

    def to_dict(self):
        def _safe_str(val):
            return "" if val is None else str(val)

        return {
            "id": self.id,
            "timestamp": self.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            if self.timestamp
            else "",
            "photo": self.photo,
            "memo": self.memo or "",
            "status": self.status,
            "info": {
                "name": self.name,
                "birth": self.birth.strftime("%Y-%m-%d") if self.birth else "",
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
                "interview_date": self.interview_date.strftime("%Y-%m-%d")
                if self.interview_date
                else "",
                "start_date": self.start_date.strftime("%Y-%m-%d")
                if self.start_date
                else "",
                "agree": "on" if self.agree else "off",
            },
            "extra": {
                "advance_pay": self.advance_pay,
                "insurance_type": self.insurance_type,
            },
        }


class Career(db.Model):
    __tablename__ = "careers"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    application_id = db.Column(
        db.String(36), db.ForeignKey("applications.id"), nullable=False, index=True
    )
    company = db.Column(db.String(100))
    start = db.Column(db.Date)
    end = db.Column(db.Date)
    role = db.Column(db.String(100))
    reason = db.Column(db.String(200))

    def to_dict(self):
        return {
            "company": self.company,
            "start": self.start.strftime("%Y-%m-%d") if self.start else "",
            "end": self.end.strftime("%Y-%m-%d") if self.end else "",
            "role": self.role,
            "reason": self.reason,
        }
