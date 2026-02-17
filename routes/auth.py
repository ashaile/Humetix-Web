import os
import time
import logging
import hashlib
import json
from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, session, flash

# Logger 설정
logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__)

ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD')
if not ADMIN_PASSWORD:
    raise RuntimeError("ADMIN_PASSWORD environment variable is not set")

# 파일 기반 속도 제한 (멀티워커 환경 대응)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RATE_LIMIT_FILE = os.path.join(BASE_DIR, 'logs', 'login_attempts.json')
MAX_ATTEMPTS = 5
BLOCK_TIME = 300  # 5분

def _load_attempts():
    """파일에서 로그인 시도 기록을 로드"""
    try:
        if os.path.exists(RATE_LIMIT_FILE):
            with open(RATE_LIMIT_FILE, 'r') as f:
                return json.load(f)
    except (json.JSONDecodeError, IOError):
        pass
    return {}

def _save_attempts(attempts):
    """로그인 시도 기록을 파일에 저장"""
    try:
        os.makedirs(os.path.dirname(RATE_LIMIT_FILE), exist_ok=True)
        with open(RATE_LIMIT_FILE, 'w') as f:
            json.dump(attempts, f)
    except IOError as e:
        logger.error(f"Failed to save login attempts: {e}")

def cleanup_attempts(ip):
    """만료된 시도 기록 정리"""
    attempts = _load_attempts()
    now = time.time()
    if ip in attempts:
        attempts[ip] = [t for t in attempts[ip] if now - t < BLOCK_TIME]
        if not attempts[ip]:
            del attempts[ip]
    _save_attempts(attempts)
    return attempts

def _check_password(input_password):
    """타이밍 공격 방지를 위한 비밀번호 비교"""
    input_hash = hashlib.sha256(input_password.encode()).hexdigest()
    correct_hash = hashlib.sha256(ADMIN_PASSWORD.encode()).hexdigest()
    return input_hash == correct_hash

def admin_required(f):
    """관리자 인증 확인 데코레이터"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('is_admin'):
            flash('관리자 로그인이 필요합니다.', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        ip = request.remote_addr
        attempts = cleanup_attempts(ip)

        if len(attempts.get(ip, [])) >= MAX_ATTEMPTS:
            logger.warning(f"Login blocked for IP {ip} due to too many failed attempts")
            flash('너무 많은 로그인 시도가 있었습니다. 5분 후 다시 시도해주세요.', 'danger')
            return redirect(url_for('auth.login'))

        password = request.form.get('password')
        if _check_password(password):
            # 세션 재생성 (세션 고정 공격 방지)
            session.clear()
            session['is_admin'] = True
            session.permanent = True
            # 로그인 성공 시 시도 기록 초기화
            attempts = _load_attempts()
            if ip in attempts:
                del attempts[ip]
            _save_attempts(attempts)
            logger.info(f"Admin login success from {ip}")
            return redirect(url_for('admin.master_view'))
        else:
            # 실패 기록
            attempts = _load_attempts()
            if ip not in attempts:
                attempts[ip] = []
            attempts[ip].append(time.time())
            _save_attempts(attempts)
            logger.warning(f"Admin login failed from {ip}")

            # 무차별 대입 방지용 지연
            time.sleep(1)
            flash('비밀번호가 틀렸습니다.', 'danger')
            return redirect(url_for('auth.login'))
    return render_template('login.html')

@auth_bp.route('/logout')
def logout():
    session.pop('is_admin', None)
    flash('로그아웃 되었습니다.', 'info')
    return redirect(url_for('index'))
