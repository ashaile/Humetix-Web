import os
import hmac
import time
import logging
from flask import Blueprint, render_template, request, redirect, url_for, session

# Logger 설정
logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__)

ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD')
if not ADMIN_PASSWORD:
    raise RuntimeError("ADMIN_PASSWORD environment variable is not set")

# 간단한 인메모리 속도 제한: IP -> 타임스탬프 리스트
LOGIN_ATTEMPTS = {}
MAX_ATTEMPTS = 5
BLOCK_TIME = 300  # 5분

def cleanup_attempts(ip):
    now = time.time()
    if ip in LOGIN_ATTEMPTS:
        LOGIN_ATTEMPTS[ip] = [t for t in LOGIN_ATTEMPTS[ip] if now - t < BLOCK_TIME]
        if not LOGIN_ATTEMPTS[ip]:
            del LOGIN_ATTEMPTS[ip]

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        ip = request.remote_addr
        cleanup_attempts(ip)
        
        if len(LOGIN_ATTEMPTS.get(ip, [])) >= MAX_ATTEMPTS:
            logger.warning(f"Login blocked for IP {ip} due to too many failed attempts")
            return "<script>alert('너무 많은 로그인 시도가 있었습니다. 5분 후 다시 시도해주세요.'); history.back();</script>"
            
        password = request.form.get('password')
        if password and hmac.compare_digest(password, ADMIN_PASSWORD):
            session['is_admin'] = True
            # 로그인 성공 시 시도 기록 초기화
            if ip in LOGIN_ATTEMPTS:
                del LOGIN_ATTEMPTS[ip]
            logger.info(f"Admin login success from {ip}")
            return redirect(url_for('admin.master_view'))
        else:
            # 실패 기록
            if ip not in LOGIN_ATTEMPTS:
                LOGIN_ATTEMPTS[ip] = []
            LOGIN_ATTEMPTS[ip].append(time.time())
            logger.warning(f"Admin login failed from {ip}")
            
            # 무차별 대입 방지용 지연
            time.sleep(1)
            return "<script>alert('비밀번호가 틀렸습니다.'); history.back();</script>"
    return render_template('login.html')

@auth_bp.route('/logout')
def logout():
    session.pop('is_admin', None)
    return redirect(url_for('index'))
