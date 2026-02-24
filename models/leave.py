"""연차 관리 모델 — 잔여 요약 + 월별 발생/사용(FIFO) 추적."""

from datetime import datetime

from models._base import db


class LeaveBalance(db.Model):
    __tablename__ = "leave_balances"
    __table_args__ = (
        db.UniqueConstraint("employee_id", "year", name="uq_leave_employee_year"),
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    employee_id = db.Column(
        db.Integer,
        db.ForeignKey("employees.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    year = db.Column(db.Integer, nullable=False)
    entitled = db.Column(db.Float, nullable=False, default=0)    # 당해 발생일수
    used = db.Column(db.Float, nullable=False, default=0)        # 당해 사용일수
    remaining = db.Column(db.Float, nullable=False, default=0)   # 총 잔여 (이월 포함)
    carryover = db.Column(db.Float, nullable=False, default=0)   # 이월 일수
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    employee = db.relationship("Employee", backref=db.backref("leave_balances", lazy=True))

    def to_dict(self):
        return {
            "id": self.id,
            "employee_id": self.employee_id,
            "employee_name": self.employee.name if self.employee else "",
            "year": self.year,
            "entitled": self.entitled,
            "used": self.used,
            "remaining": self.remaining,
            "carryover": self.carryover,
        }


class LeaveAccrual(db.Model):
    """월별 연차/월차 발생(적립) 기록.

    month=0 : 1년 이상 근무자의 연초 일괄 발생 (15일+)
    month=1~12 : 만근 월차 (각 1일)
    remaining : FIFO 잔여 — 사용 시 가장 오래된 것부터 차감.
    """

    __tablename__ = "leave_accruals"
    __table_args__ = (
        db.UniqueConstraint("employee_id", "year", "month", name="uq_accrual_emp_ym"),
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    employee_id = db.Column(
        db.Integer,
        db.ForeignKey("employees.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    year = db.Column(db.Integer, nullable=False)
    month = db.Column(db.Integer, nullable=False)  # 0=일괄, 1~12=월별
    accrual_type = db.Column(db.String(20), nullable=False, default="monthly")
    days = db.Column(db.Float, nullable=False, default=1.0)
    remaining = db.Column(db.Float, nullable=False, default=1.0)
    description = db.Column(db.String(100), default="")
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    employee = db.relationship("Employee", backref=db.backref("leave_accruals", lazy=True))
    usage_links = db.relationship("LeaveUsage", back_populates="accrual", lazy=True)

    def to_dict(self):
        return {
            "id": self.id,
            "employee_id": self.employee_id,
            "year": self.year,
            "month": self.month,
            "accrual_type": self.accrual_type,
            "days": self.days,
            "remaining": self.remaining,
            "description": self.description,
        }


class LeaveUsage(db.Model):
    """연차 사용 기록 — FIFO로 어떤 발생분에서 차감됐는지 추적."""

    __tablename__ = "leave_usages"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    employee_id = db.Column(
        db.Integer,
        db.ForeignKey("employees.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    accrual_id = db.Column(
        db.Integer,
        db.ForeignKey("leave_accruals.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    use_date = db.Column(db.Date, nullable=False)
    days = db.Column(db.Float, nullable=False, default=1.0)
    description = db.Column(db.String(100), default="")
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    employee = db.relationship("Employee", backref=db.backref("leave_usages", lazy=True))
    accrual = db.relationship("LeaveAccrual", back_populates="usage_links")

    def to_dict(self):
        accrual_label = ""
        if self.accrual:
            if self.accrual.month == 0:
                accrual_label = f"{self.accrual.year}년 일괄"
            else:
                accrual_label = f"{self.accrual.year}년 {self.accrual.month}월분"
        return {
            "id": self.id,
            "employee_id": self.employee_id,
            "accrual_id": self.accrual_id,
            "accrual_label": accrual_label,
            "use_date": self.use_date.isoformat() if self.use_date else "",
            "days": self.days,
            "description": self.description,
        }
