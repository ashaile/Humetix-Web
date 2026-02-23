import os
import re
from functools import wraps

from flask import jsonify, redirect, request, session, url_for

# ── 공통 상수 ──
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
ENV_FILE_PATH = os.path.join(BASE_DIR, ".env")

# ── 유효성 검사 ──
MONTH_PATTERN = re.compile(r"^\d{4}-\d{2}$")


def validate_month(month: str) -> bool:
    """YYYY-MM 형식 월 유효성 검사"""
    if not MONTH_PATTERN.fullmatch(month or ""):
        return False
    year, mon = month.split("-")
    return int(year) >= 2000 and 1 <= int(mon) <= 12


# ── 인증 데코레이터 ──
def require_admin(f):
    """관리자 세션 인증 데코레이터.

    GET 요청: 미인증 시 login 페이지로 redirect
    그 외: 미인증 시 JSON 401 응답
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("is_admin"):
            if request.method == "GET":
                return redirect(url_for("auth.login"))
            return jsonify({"error": "권한이 없습니다.", "success": False,
                            "message": "권한이 없습니다."}), 401
        return f(*args, **kwargs)

    return decorated_function
