"""급여 설정 계층 해석 서비스.

우선순위: employee 개별 설정 > site 현장 설정 > system 기본값
각 필드별로 독립적으로 해석 (employee에 hourly_wage만 설정하면
나머지는 site → system 순서로 폴백).
"""
import logging

from models import Employee, WageConfig, db
from models.wage_config import WAGE_DEFAULTS

logger = logging.getLogger(__name__)


def get_wage_config(employee_id=None, site_id=None):
    """직원 또는 현장에 해당하는 급여 설정을 해석하여 반환한다.

    Args:
        employee_id: 직원 ID (있으면 직원→현장→시스템 순으로 해석)
        site_id: 현장 ID (employee_id 없이 현장만 지정할 때)

    Returns:
        dict: 모든 필드가 채워진 급여 설정 딕셔너리
    """
    layers = []  # 우선순위 높은 순서대로

    if employee_id:
        # 직원 개별 설정
        emp_cfg = WageConfig.query.filter_by(
            config_type="employee", target_id=employee_id
        ).first()
        if emp_cfg:
            layers.append(emp_cfg)

        # 직원의 소속 현장 설정
        if not site_id:
            emp = db.session.get(Employee, employee_id)
            if emp and emp.site_id:
                site_id = emp.site_id

    if site_id:
        site_cfg = WageConfig.query.filter_by(
            config_type="site", target_id=site_id
        ).first()
        if site_cfg:
            layers.append(site_cfg)

    # 시스템 기본 설정 (DB)
    sys_cfg = WageConfig.query.filter_by(config_type="system").first()
    if sys_cfg:
        layers.append(sys_cfg)

    # 필드별로 우선순위 해석
    result = {}
    for field in WageConfig.RATE_FIELDS:
        value = None
        for layer in layers:
            v = getattr(layer, field, None)
            if v is not None:
                value = v
                break
        if value is None:
            value = WAGE_DEFAULTS.get(field)
        result[field] = value

    return result


def get_wage_config_detail(employee_id):
    """디버그/관리 UI용 — 각 필드의 출처도 함께 반환.

    Returns:
        list of dict: [{field, value, source, source_name}, ...]
    """
    emp = db.session.get(Employee, employee_id)
    if not emp:
        return []

    layers = []

    emp_cfg = WageConfig.query.filter_by(
        config_type="employee", target_id=employee_id
    ).first()
    if emp_cfg:
        layers.append(("employee", f"직원: {emp.name}", emp_cfg))

    if emp.site_id:
        site_cfg = WageConfig.query.filter_by(
            config_type="site", target_id=emp.site_id
        ).first()
        if site_cfg:
            site_name = emp.site.name if emp.site else str(emp.site_id)
            layers.append(("site", f"현장: {site_name}", site_cfg))

    sys_cfg = WageConfig.query.filter_by(config_type="system").first()
    if sys_cfg:
        layers.append(("system", "시스템 설정", sys_cfg))

    FIELD_LABELS = {
        "wage_type": "급여유형",
        "hourly_wage": "시급",
        "daily_wage": "일당 (1공)",
        "standard_work_hours": "기본 근무시간",
        "break_hours": "휴게시간",
        "overtime_rate": "연장근로 배율",
        "night_bonus_rate": "야간근로 가산",
        "unpaid_holiday_rate": "무급휴일 배율",
        "paid_holiday_rate": "유급휴일 배율",
        "paid_holiday_ot_rate": "유급휴일 초과 배율",
        "overtime_unit": "잔업 계산방식",
        "overtime_fixed_amount": "잔업 시간당 금액",
        "calc_method": "급여 산정방식",
    }

    details = []
    for field in WageConfig.RATE_FIELDS:
        value = None
        source = "default"
        source_name = "기본값"
        for src_type, src_label, cfg in layers:
            v = getattr(cfg, field, None)
            if v is not None:
                value = v
                source = src_type
                source_name = src_label
                break
        if value is None:
            value = WAGE_DEFAULTS.get(field)
        details.append({
            "field": field,
            "label": FIELD_LABELS.get(field, field),
            "value": value,
            "source": source,
            "source_name": source_name,
        })
    return details


def save_wage_config(config_type, target_id, data):
    """급여 설정을 저장 또는 갱신한다.

    Args:
        config_type: 'system', 'site', 'employee'
        target_id: site_id 또는 employee_id (system이면 None)
        data: {field: value} 딕셔너리 (None이면 해당 필드를 상위로 위임)

    Returns:
        WageConfig: 저장된 설정 객체
    """
    cfg = WageConfig.query.filter_by(
        config_type=config_type, target_id=target_id
    ).first()

    if not cfg:
        cfg = WageConfig(config_type=config_type, target_id=target_id)
        db.session.add(cfg)

    for field in WageConfig.RATE_FIELDS:
        if field in data:
            val = data[field]
            # 빈 문자열이나 None → null (상위로 위임)
            if val == "" or val is None:
                setattr(cfg, field, None)
            elif field in WageConfig.STR_FIELDS:
                setattr(cfg, field, str(val))
            elif field in WageConfig.INT_FIELDS:
                setattr(cfg, field, int(val))
            else:
                setattr(cfg, field, float(val))

    db.session.commit()
    logger.info("WageConfig saved: type=%s, target=%s", config_type, target_id)
    return cfg
