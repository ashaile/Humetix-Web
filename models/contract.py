"""전자계약서 모델 — Glosign 스타일 서식/계약/참여자 + 감사 로그."""

import json
from datetime import datetime

from models._base import db


class ContractTemplate(db.Model):
    """서식 (PDF 업로드 + 필드 배치 정보)."""

    __tablename__ = "contract_templates"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False)
    file_path = db.Column(db.String(300), nullable=False)
    file_original_name = db.Column(db.String(200), default="")
    page_count = db.Column(db.Integer, nullable=False, default=1)
    fields_json = db.Column(db.Text, default="[]")
    roles_json = db.Column(
        db.Text,
        default='[{"key":"employer","label":"사용자"},{"key":"worker","label":"근로자"}]',
    )
    status = db.Column(db.String(10), nullable=False, default="active")
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    contracts = db.relationship("Contract", back_populates="template", lazy=True)

    @property
    def fields(self):
        try:
            return json.loads(self.fields_json or "[]")
        except (json.JSONDecodeError, TypeError):
            return []

    @fields.setter
    def fields(self, value):
        self.fields_json = json.dumps(value, ensure_ascii=False)

    @property
    def roles(self):
        try:
            return json.loads(self.roles_json or "[]")
        except (json.JSONDecodeError, TypeError):
            return []

    @roles.setter
    def roles(self, value):
        self.roles_json = json.dumps(value, ensure_ascii=False)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "file_original_name": self.file_original_name,
            "page_count": self.page_count,
            "fields": self.fields,
            "roles": self.roles,
            "status": self.status,
            "contract_count": len(self.contracts),
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M") if self.created_at else "",
        }


class Contract(db.Model):
    """계약 인스턴스."""

    __tablename__ = "contracts"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    template_id = db.Column(
        db.Integer,
        db.ForeignKey("contract_templates.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    title = db.Column(db.String(200), nullable=False)
    employee_id = db.Column(
        db.Integer,
        db.ForeignKey("employees.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status = db.Column(db.String(20), nullable=False, default="draft")
    scheduled_at = db.Column(db.DateTime, nullable=True)
    expires_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    completed_at = db.Column(db.DateTime, nullable=True)
    final_pdf_path = db.Column(db.String(300), nullable=True)
    batch_id = db.Column(db.String(36), nullable=True, index=True)

    template = db.relationship("ContractTemplate", back_populates="contracts")
    employee = db.relationship("Employee", backref=db.backref("contracts", lazy=True))
    participants = db.relationship(
        "ContractParticipant", back_populates="contract", lazy=True, cascade="all, delete-orphan"
    )
    audit_logs = db.relationship(
        "ContractAuditLog", back_populates="contract", lazy=True, cascade="all, delete-orphan"
    )

    @property
    def is_expired(self):
        if not self.expires_at:
            return False
        return datetime.now() > self.expires_at

    @property
    def is_scheduled(self):
        return self.status == "scheduled"

    def to_dict(self):
        return {
            "id": self.id,
            "template_id": self.template_id,
            "template_name": self.template.name if self.template else "",
            "title": self.title,
            "employee_id": self.employee_id,
            "employee_name": self.employee.name if self.employee else "",
            "status": self.status,
            "scheduled_at": self.scheduled_at.strftime("%Y-%m-%d %H:%M") if self.scheduled_at else "",
            "expires_at": self.expires_at.strftime("%Y-%m-%d %H:%M") if self.expires_at else "",
            "is_expired": self.is_expired,
            "is_scheduled": self.is_scheduled,
            "participants": [p.to_dict() for p in self.participants],
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M") if self.created_at else "",
            "completed_at": self.completed_at.strftime("%Y-%m-%d %H:%M") if self.completed_at else "",
            "batch_id": self.batch_id,
        }


class ContractParticipant(db.Model):
    """계약 참여자 (서명자)."""

    __tablename__ = "contract_participants"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    contract_id = db.Column(
        db.Integer,
        db.ForeignKey("contracts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role_key = db.Column(db.String(20), nullable=False)
    name = db.Column(db.String(50), nullable=False)
    phone = db.Column(db.String(20), default="")
    sign_token = db.Column(db.String(64), unique=True, nullable=False, index=True)
    status = db.Column(db.String(10), nullable=False, default="pending")
    field_values_json = db.Column(db.Text, default="[]")
    signed_at = db.Column(db.DateTime, nullable=True)
    sign_ip = db.Column(db.String(45), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now)

    contract = db.relationship("Contract", back_populates="participants")

    @property
    def field_values(self):
        try:
            return json.loads(self.field_values_json or "[]")
        except (json.JSONDecodeError, TypeError):
            return []

    @field_values.setter
    def field_values(self, value):
        self.field_values_json = json.dumps(value, ensure_ascii=False)

    def to_dict(self):
        return {
            "id": self.id,
            "role_key": self.role_key,
            "name": self.name,
            "phone": self.phone,
            "sign_token": self.sign_token,
            "status": self.status,
            "signed_at": self.signed_at.strftime("%Y-%m-%d %H:%M") if self.signed_at else "",
        }


class ContractAuditLog(db.Model):
    """계약 감사 로그."""

    __tablename__ = "contract_audit_logs"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    contract_id = db.Column(
        db.Integer,
        db.ForeignKey("contracts.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    action = db.Column(db.String(50), nullable=False)
    actor = db.Column(db.String(100), default="")
    detail = db.Column(db.Text, default="")
    ip_address = db.Column(db.String(45), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now)

    contract = db.relationship("Contract", back_populates="audit_logs")

    def to_dict(self):
        return {
            "id": self.id,
            "contract_id": self.contract_id,
            "action": self.action,
            "actor": self.actor,
            "detail": self.detail,
            "ip_address": self.ip_address or "",
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else "",
        }
