from datetime import datetime

from models._base import db


class AdvanceRequest(db.Model):
    __tablename__ = "advance_requests"
    __table_args__ = (
        db.Index("ix_advance_employee_month", "employee_id", "request_month"),
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
    request_month = db.Column(db.String(7), nullable=False, index=True)
    work_type = db.Column(db.String(10), nullable=False, default="weekly")
    amount = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.Text, default="")
    status = db.Column(db.String(20), nullable=False, default="pending", index=True)
    admin_comment = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.now)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    employee = db.relationship("Employee", back_populates="advance_requests")

    def to_dict(self):
        return {
            "id": self.id,
            "employee_id": self.employee_id,
            "emp_id": self.employee_id,
            "birth_date": self.birth_date,
            "emp_name": self.emp_name,
            "dept": self.dept,
            "request_month": self.request_month,
            "amount": self.amount,
            "reason": self.reason,
            "status": self.status,
            "admin_comment": self.admin_comment,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M") if self.created_at else "",
            "reviewed_at": self.reviewed_at.strftime("%Y-%m-%d %H:%M") if self.reviewed_at else "",
        }
