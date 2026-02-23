from datetime import datetime

from models._base import db


class Site(db.Model):
    __tablename__ = "sites"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False, unique=True, index=True)
    address = db.Column(db.String(200), default="")
    contact_person = db.Column(db.String(50), default="")
    contact_phone = db.Column(db.String(20), default="")
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    employees = db.relationship("Employee", back_populates="site", lazy=True)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "address": self.address,
            "contact_person": self.contact_person,
            "contact_phone": self.contact_phone,
            "is_active": self.is_active,
            "employee_count": len([e for e in self.employees if e.is_active]),
        }
