from datetime import datetime

from models._base import db


class Payslip(db.Model):
    __tablename__ = "payslips"
    __table_args__ = (
        db.UniqueConstraint("employee_id", "month", name="uq_payslip_employee_month"),
        db.Index("ix_payslip_employee_month", "employee_id", "month"),
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    employee_id = db.Column(
        db.Integer,
        db.ForeignKey("employees.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    emp_name = db.Column(db.String(50), nullable=False)
    dept = db.Column(db.String(50), default="")
    month = db.Column(db.String(7), nullable=False, index=True)
    salary_mode = db.Column(db.String(10), default="standard")
    total_work_hours = db.Column(db.Float, nullable=False, default=0.0)
    ot_hours = db.Column(db.Float, nullable=False, default=0.0)
    night_hours = db.Column(db.Float, nullable=False, default=0.0)
    holiday_hours = db.Column(db.Float, nullable=False, default=0.0)
    base_salary = db.Column(db.Integer, nullable=False, default=0)
    ot_pay = db.Column(db.Integer, nullable=False, default=0)
    night_pay = db.Column(db.Integer, nullable=False, default=0)
    holiday_pay = db.Column(db.Integer, nullable=False, default=0)
    gross = db.Column(db.Integer, nullable=False, default=0)
    tax = db.Column(db.Integer, nullable=False, default=0)
    insurance = db.Column(db.Integer, nullable=False, default=0)
    advance_deduction = db.Column(db.Integer, nullable=False, default=0)
    net = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    employee = db.relationship("Employee", back_populates="payslips")

    def to_dict(self):
        return {
            "id": self.id,
            "employee_id": self.employee_id,
            "emp_id": self.employee_id,
            "emp_name": self.emp_name,
            "dept": self.dept,
            "month": self.month,
            "salary_mode": self.salary_mode,
            "total_work_hours": self.total_work_hours,
            "ot_hours": self.ot_hours,
            "night_hours": self.night_hours,
            "holiday_hours": self.holiday_hours,
            "base_salary": self.base_salary,
            "ot_pay": self.ot_pay,
            "night_pay": self.night_pay,
            "holiday_pay": self.holiday_pay,
            "gross": self.gross,
            "tax": self.tax,
            "insurance": self.insurance,
            "advance_deduction": self.advance_deduction,
            "net": self.net,
        }
