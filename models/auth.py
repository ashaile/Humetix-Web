from datetime import datetime

from models._base import db


class AdminLoginAttempt(db.Model):
    __tablename__ = "admin_login_attempts"
    __table_args__ = (db.Index("ix_admin_login_attempt_ip_created", "ip", "created_at"),)

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    ip = db.Column(db.String(64), nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
