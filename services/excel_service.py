"""Excel 빌드 관련 헬퍼 (admin 라우트에서 추출)"""
from datetime import datetime

EXCEL_COLUMNS = [
    ("name", "이름"),
    ("phone", "연락처"),
    ("email", "이메일"),
    ("address", "희망지역/주소"),
    ("status", "상태"),
    ("submitted_at", "접수일"),
    ("gender", "성별"),
    ("birth", "생년월일"),
    ("shift", "근무형태"),
    ("posture", "근무방식"),
    ("overtime", "잔업"),
    ("holiday", "특근"),
    ("advance_pay", "가불여부"),
    ("insurance_type", "급여형태"),
    ("interview_date", "면접일"),
    ("start_date", "출근가능일"),
    ("memo", "관리자메모"),
]
EXCEL_COLUMN_LABELS = dict(EXCEL_COLUMNS)
EXCEL_COLUMN_KEYS = {key for key, _ in EXCEL_COLUMNS}
DEFAULT_EXCEL_COLUMNS = ["name", "phone", "email", "address", "status", "submitted_at"]


def _to_date_text(value):
    if not value:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return value.strftime("%Y-%m-%d")


def _status_text(status):
    return {
        "new": "신규",
        "review": "검토",
        "interview": "면접",
        "offer": "오퍼",
        "hired": "합격",
        "rejected": "불합격",
    }.get(status or "", status or "")


def _excel_row_values(app):
    return {
        "name": app.name or "",
        "phone": app.phone or "",
        "email": app.email or "",
        "address": app.address or "",
        "status": _status_text(app.status),
        "submitted_at": _to_date_text(app.timestamp),
        "gender": app.gender or "",
        "birth": _to_date_text(app.birth),
        "shift": app.shift or "",
        "posture": app.posture or "",
        "overtime": app.overtime or "",
        "holiday": app.holiday or "",
        "advance_pay": app.advance_pay or "",
        "insurance_type": app.insurance_type or "",
        "interview_date": _to_date_text(app.interview_date),
        "start_date": _to_date_text(app.start_date),
        "memo": app.memo or "",
    }


def parse_excel_columns(raw_columns):
    if raw_columns is None:
        return None

    keys = []
    for token in str(raw_columns).split(","):
        key = token.strip()
        if key and key in EXCEL_COLUMN_KEYS and key not in keys:
            keys.append(key)

    return keys or list(DEFAULT_EXCEL_COLUMNS)
