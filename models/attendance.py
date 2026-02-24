from datetime import datetime

from models._base import db


class AttendanceRecord(db.Model):
    __tablename__ = "attendance_records"
    __table_args__ = (
        db.Index("ix_attendance_employee_date", "employee_id", "work_date"),
        db.UniqueConstraint("employee_id", "work_date", name="uq_attendance_employee_date"),
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    employee_id = db.Column(
        db.Integer,
        db.ForeignKey("employees.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    birth_date = db.Column(db.String(6), nullable=False)
    emp_name = db.Column(db.String(50), nullable=False)
    dept = db.Column(db.String(50), default="")
    work_date = db.Column(db.Date, nullable=False, index=True)
    clock_in = db.Column(db.String(5), nullable=True)
    clock_out = db.Column(db.String(5), nullable=True)
    work_type = db.Column(db.String(20), nullable=False, default="normal")
    total_work_hours = db.Column(db.Float, nullable=False, default=0.0)
    overtime_hours = db.Column(db.Float, nullable=False, default=0.0)
    night_hours = db.Column(db.Float, nullable=False, default=0.0)
    holiday_work_hours = db.Column(db.Float, nullable=False, default=0.0)
    source = db.Column(db.String(20), nullable=False, default="employee")
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    employee = db.relationship("Employee", back_populates="attendance_records")

    def to_dict(self):
        return {
            "id": self.id,
            "employee_id": self.employee_id,
            "emp_id": self.employee_id,
            "birth_date": self.birth_date,
            "emp_name": self.emp_name,
            "dept": self.dept,
            "work_date": self.work_date.strftime("%Y-%m-%d") if self.work_date else "",
            "clock_in": self.clock_in or "",
            "clock_out": self.clock_out or "",
            "work_type": self.work_type,
            "total_work_hours": self.total_work_hours,
            "overtime_hours": self.overtime_hours,
            "night_hours": self.night_hours,
            "holiday_work_hours": self.holiday_work_hours,
            "source": self.source or "employee",
        }


class OperationCalendarDay(db.Model):
    __tablename__ = "operation_calendar_days"
    __table_args__ = (
        db.UniqueConstraint("work_date", name="uq_operation_calendar_work_date"),
        db.Index("ix_operation_calendar_work_date", "work_date"),
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    work_date = db.Column(db.Date, nullable=False, index=True)
    day_type = db.Column(db.String(20), nullable=False, default="workday")
    note = db.Column(db.String(200), default="")
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    def to_dict(self):
        return {
            "id": self.id,
            "work_date": self.work_date.strftime("%Y-%m-%d") if self.work_date else "",
            "day_type": self.day_type,
            "note": self.note or "",
        }
