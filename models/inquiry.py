from datetime import datetime

from models._base import db


class Inquiry(db.Model):
    __tablename__ = "inquiries"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    created_at = db.Column(db.DateTime, default=datetime.now, index=True)
    updated_at = db.Column(
        db.DateTime, default=datetime.now, onupdate=datetime.now, index=True
    )
    company = db.Column(db.String(100), nullable=False, index=True)
    name = db.Column(db.String(50), nullable=False, index=True)
    phone = db.Column(db.String(30), nullable=False, index=True)
    email = db.Column(db.String(100), index=True)
    message = db.Column(db.Text)
    status = db.Column(db.String(20), default="new", index=True)
    assignee = db.Column(db.String(50))
    admin_memo = db.Column(db.Text)
