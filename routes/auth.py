import hmac
import logging
import os
import time
from datetime import datetime, timedelta

from dotenv import dotenv_values
from flask import Blueprint, current_app, redirect, render_template, request, session, url_for

from models import AdminLoginAttempt, db

logger = logging.getLogger(__name__)

auth_bp = Blueprint("auth", __name__)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_FILE_PATH = os.path.join(BASE_DIR, ".env")


def _get_admin_password() -> str:
    file_password = dotenv_values(ENV_FILE_PATH).get("ADMIN_PASSWORD")
    if file_password:
        return str(file_password)
    return os.environ.get("ADMIN_PASSWORD", "")


def _client_ip() -> str:
    forwarded_for = request.headers.get("X-Forwarded-For", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.remote_addr or "unknown"


def _recent_attempt_count(ip: str, block_seconds: int) -> int:
    cutoff = datetime.now() - timedelta(seconds=block_seconds)
    return AdminLoginAttempt.query.filter(
        AdminLoginAttempt.ip == ip,
        AdminLoginAttempt.created_at >= cutoff,
    ).count()


def _clear_attempts(ip: str) -> None:
    AdminLoginAttempt.query.filter(AdminLoginAttempt.ip == ip).delete()


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        ip = _client_ip()
        max_attempts = int(current_app.config.get("LOGIN_MAX_ATTEMPTS", 5))
        block_seconds = int(current_app.config.get("LOGIN_BLOCK_SECONDS", 300))
        admin_password = _get_admin_password()

        if not admin_password:
            logger.error("ADMIN_PASSWORD environment variable is not set")
            return "<script>alert('서버 설정 오류: 관리자 비밀번호가 설정되지 않았습니다.'); history.back();</script>"

        if _recent_attempt_count(ip, block_seconds) >= max_attempts:
            logger.warning("Login blocked for IP %s due to too many failed attempts", ip)
            return (
                "<script>alert('로그인 시도가 너무 많습니다. 5분 후 다시 시도해주세요.'); history.back();</script>"
            )

        password = request.form.get("password")
        if password and hmac.compare_digest(password, admin_password):
            try:
                _clear_attempts(ip)
                db.session.commit()
            except Exception:
                db.session.rollback()

            session.clear()
            session["is_admin"] = True
            session.permanent = True
            logger.info("Admin login success from %s", ip)
            return redirect(url_for("admin.master_view"))

        try:
            db.session.add(AdminLoginAttempt(ip=ip))
            db.session.commit()
        except Exception:
            db.session.rollback()

        logger.warning("Admin login failed from %s", ip)
        time.sleep(1)
        return "<script>alert('비밀번호가 틀렸습니다.'); history.back();</script>"

    return render_template("login.html")


@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))
