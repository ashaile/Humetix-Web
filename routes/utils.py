import re

MONTH_PATTERN = re.compile(r"^\d{4}-\d{2}$")


def validate_month(month: str) -> bool:
    """YYYY-MM 형식 월 유효성 검사"""
    if not MONTH_PATTERN.fullmatch(month or ""):
        return False
    year, mon = month.split("-")
    return int(year) >= 2000 and 1 <= int(mon) <= 12
