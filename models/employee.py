from datetime import datetime

from models._base import db


class Employee(db.Model):
    __tablename__ = "employees"
    __table_args__ = (
        db.UniqueConstraint("name", "birth_date", name="uq_employee_name_birth"),
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(50), nullable=False, index=True)
    birth_date = db.Column(db.String(6), nullable=False)
    work_type = db.Column(db.String(10), nullable=False, default="weekly")
    hire_date = db.Column(db.Date, nullable=True)
    resign_date = db.Column(db.Date, nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    attendance_records = db.relationship(
        "AttendanceRecord", back_populates="employee", lazy=True
    )
    advance_requests = db.relationship(
        "AdvanceRequest", back_populates="employee", lazy=True
    )
    payslips = db.relationship("Payslip", back_populates="employee", lazy=True)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "birth_date": self.birth_date,
            "work_type": self.work_type,
            "hire_date": self.hire_date.strftime("%Y-%m-%d") if self.hire_date else "",
            "resign_date": self.resign_date.strftime("%Y-%m-%d") if self.resign_date else "",
            "is_active": self.is_active,
            "created_at": self.created_at.strftime("%Y-%m-%d") if self.created_at else "",
        }
