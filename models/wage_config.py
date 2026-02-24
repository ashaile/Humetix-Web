"""현장별/직원별 급여 설정 모델.

우선순위: employee > site > system (기본값)
"""
from datetime import datetime

from models._base import db


# 시스템 기본값 (config.py 값과 동일)
WAGE_DEFAULTS = {
    "wage_type": "hourly",
    "hourly_wage": 10_320,
    "daily_wage": None,
    "standard_work_hours": 8.0,
    "break_hours": 1.0,
    "overtime_rate": 1.5,
    "night_bonus_rate": 0.5,
    "unpaid_holiday_rate": 1.5,
    "paid_holiday_rate": 1.5,
    "paid_holiday_ot_rate": 2.0,
    "overtime_unit": "rate",
    "overtime_fixed_amount": None,
    "calc_method": None,
}


class WageConfig(db.Model):
    __tablename__ = "wage_configs"
    __table_args__ = (
        db.UniqueConstraint("config_type", "target_id", name="uq_wage_config_type_target"),
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    config_type = db.Column(db.String(10), nullable=False)  # 'system', 'site', 'employee'
    target_id = db.Column(db.Integer, nullable=True)         # site_id 또는 employee_id, system이면 null

    wage_type = db.Column(db.String(10), nullable=True)              # 'hourly'(시급제) / 'daily'(공수제)
    hourly_wage = db.Column(db.Integer, nullable=True)               # 시급
    daily_wage = db.Column(db.Integer, nullable=True)                # 일당 (1공 단가)
    standard_work_hours = db.Column(db.Float, nullable=True)         # 기본 근무시간
    break_hours = db.Column(db.Float, nullable=True)                 # 휴게시간
    overtime_rate = db.Column(db.Float, nullable=True)               # 연장근로 배율
    night_bonus_rate = db.Column(db.Float, nullable=True)            # 야간근로 가산 배율
    unpaid_holiday_rate = db.Column(db.Float, nullable=True)         # 무급휴일 배율
    paid_holiday_rate = db.Column(db.Float, nullable=True)           # 유급휴일 기본 배율 (8h 이내)
    paid_holiday_ot_rate = db.Column(db.Float, nullable=True)        # 유급휴일 초과 배율 (8h 초과)
    overtime_unit = db.Column(db.String(10), nullable=True)          # 'rate'(배율) / 'fixed'(시간당 정액)
    overtime_fixed_amount = db.Column(db.Integer, nullable=True)     # 잔업 시간당 정액 금액
    calc_method = db.Column(db.String(15), nullable=True)           # 'standard'(209h차감) / 'daily_build'(일급제) / 'actual'(실근무)

    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    # 설정 가능한 필드 목록
    RATE_FIELDS = [
        "wage_type", "hourly_wage", "daily_wage",
        "standard_work_hours", "break_hours",
        "overtime_rate", "night_bonus_rate",
        "unpaid_holiday_rate", "paid_holiday_rate", "paid_holiday_ot_rate",
        "overtime_unit", "overtime_fixed_amount",
        "calc_method",
    ]
    INT_FIELDS = {"hourly_wage", "daily_wage", "overtime_fixed_amount"}
    STR_FIELDS = {"wage_type", "overtime_unit", "calc_method"}

    def to_dict(self):
        result = {
            "id": self.id,
            "config_type": self.config_type,
            "target_id": self.target_id,
        }
        for field in self.RATE_FIELDS:
            result[field] = getattr(self, field)
        return result
