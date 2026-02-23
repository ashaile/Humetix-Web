import hmac
import logging
import os
import time
from datetime import datetime, timedelta

import bcrypt
from dotenv import dotenv_values
from flask import Blueprint, current_app, redirect, render_template, request, session, url_for

from models import AdminLoginAttempt, db
from routes.utils import ENV_FILE_PATH

logger = logging.getLogger(__name__)

auth_bp = Blueprint("auth", __name__)


def _get_admin_password() -> str:
    file_password = dotenv_values(ENV_FILE_PATH).get("ADMIN_PASSWORD")
    if file_password:
        return str(file_password)
    return os.environ.get("ADMIN_PASSWORD", "")


def _is_bcrypt_hash(value: str) -> bool:
    return value.startswith("$2b$") or value.startswith("$2a$")


def _verify_password(plain: str, stored: str) -> bool:
    """bcrypt 해시면 해시 비교, 아니면 평문 비교."""
    if _is_bcrypt_hash(stored):
        try:
            return bcrypt.checkpw(plain.encode("utf-8"), stored.encode("utf-8"))
        except Exception:
            return False
    return hmac.compare_digest(plain, stored)


def _migrate_to_hash(stored: str) -> None:
    """저장된 비밀번호가 평문이면 bcrypt 해시로 .env 파일 업데이트."""
    if _is_bcrypt_hash(stored):
        return
    try:
        hashed = bcrypt.hashpw(stored.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        env_path = ENV_FILE_PATH
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            new_lines = []
            replaced = False
            for line in lines:
                if line.startswith("ADMIN_PASSWORD="):
                    new_lines.append(f"ADMIN_PASSWORD={hashed}\n")
                    replaced = True
                else:
                    new_lines.append(line)
            if not replaced:
                new_lines.append(f"ADMIN_PASSWORD={hashed}\n")
            with open(env_path, "w", encoding="utf-8") as f:
                f.writelines(new_lines)
            logger.info("Admin password migrated to bcrypt hash")
    except Exception as exc:
        logger.warning("Failed to migrate password to hash: %s", exc)


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


def _purge_expired_attempts(block_seconds: int) -> None:
    """만료된 로그인 시도 레코드 전체 정리 (DB 무한 증가 방지)"""
    cutoff = datetime.now() - timedelta(seconds=block_seconds)
    AdminLoginAttempt.query.filter(AdminLoginAttempt.created_at < cutoff).delete()


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        ip = _client_ip()
        max_attempts = int(current_app.config.get("LOGIN_MAX_ATTEMPTS", 5))
        block_seconds = int(current_app.config.get("LOGIN_BLOCK_SECONDS", 300))
        admin_password = _get_admin_password()

        if not admin_password:
            logger.error("ADMIN_PASSWORD environment variable is not set")
            from flask import flash
            flash("서버 설정 오류: 관리자 비밀번호가 설정되지 않았습니다.", "error")
            return redirect(url_for("auth.login"))

        try:
            _purge_expired_attempts(block_seconds)
            db.session.commit()
        except Exception:
            db.session.rollback()

        if _recent_attempt_count(ip, block_seconds) >= max_attempts:
            logger.warning("Login blocked for IP %s due to too many failed attempts", ip)
            from flask import flash
            flash("로그인 시도가 너무 많습니다. 5분 후 다시 시도해주세요.", "error")
            return redirect(url_for("auth.login"))

        password = request.form.get("password")
        if password and _verify_password(password, admin_password):
            try:
                _clear_attempts(ip)
                db.session.commit()
            except Exception:
                db.session.rollback()

            # 평문 → bcrypt 자동 마이그레이션
            _migrate_to_hash(admin_password)

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
        from flask import flash
        flash("비밀번호가 틀렸습니다.", "error")
        return redirect(url_for("auth.login"))

    return render_template("login.html")


@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))
