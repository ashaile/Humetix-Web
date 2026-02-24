import os
from flask import Flask, render_template, jsonify
from dotenv import load_dotenv
from flask_wtf.csrf import CSRFProtect
from flask_migrate import Migrate
from models import db
from extensions import limiter
from werkzeug.middleware.proxy_fix import ProxyFix

# .env 파일에서 환경변수 로드
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, '.env'), override=True)

from config import config_by_name

app = Flask(__name__)
# Nginx 프록시 뒤에서 HTTPS 관련 헤더 정보를 올바르게 처리하기 위해 적용
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

# 환경 설정 적용 (기본값 production)
env_name = os.environ.get('FLASK_ENV', 'production')
app_config = config_by_name[env_name]()
app.config.from_object(app_config)

# 로깅 설정 적용
LOG_DIR = os.path.join(BASE_DIR, 'logs')
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

from logging.config import dictConfig
dictConfig(app_config.get_logging_config(LOG_DIR))

# DB 설정은 config.py에서 일관되게 관리 (환경변수/기본값)

# 초기화
db.init_app(app)
migrate = Migrate(app, db)
csrf = CSRFProtect(app)
limiter.init_app(app)

# uploads 폴더 생성
UPLOAD_DIR = os.path.join(BASE_DIR, 'uploads')
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

# Blueprint 중앙 등록
from routes import register_blueprints
register_blueprints(app)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/privacy')
def privacy():
    return render_template('privacy.html')

@app.route('/health')
def health():
    try:
        db.session.execute(db.text('SELECT 1'))
        return jsonify({"status": "healthy", "database": "connected"}), 200
    except Exception as e:
        return jsonify({"status": "unhealthy", "database": str(e)}), 503

@app.after_request
def set_security_headers(response):
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    return response


@app.errorhandler(404)
def page_not_found(e):
    return render_template('error.html', error_code="404", error_message="페이지를 찾을 수 없습니다", error_description="요청하신 페이지가 존재하지 않거나 주소가 변경되었습니다."), 404

@app.errorhandler(500)
def internal_server_error(e):
    import logging
    logging.getLogger(__name__).exception("500 Internal Server Error: %s", e)
    return render_template('error.html', error_code="500", error_message="서버 내부 오류", error_description="잠시 후 다시 시도해주세요. 문제가 지속되면 관리자에게 문의 바랍니다."), 500

# ── 관리자 네비게이션 context_processor ──
@app.context_processor
def inject_nav_context():
    from flask import request as req

    CATEGORY_MAP = {
        'hr': [
            'admin.applications', 'employee.admin_employees',
        ],
        'work': [
            'attendance.admin_attendance', 'attendance.import_attendance',
            'attendance.admin_attendance_calendar', 'payslip.admin_payslip',
            'advance.admin_advance',
        ],
        'contract': [
            'contract.admin_templates', 'contract.admin_contracts',
            'contract.bulk_send_page', 'contract.new_contract',
            'contract.template_edit',
        ],
        'ops': [
            'site.admin_sites', 'notice.admin_notices', 'admin.inquiries',
            'leave.admin_leave', 'leave.admin_leave_detail', 'leave.admin_severance',
        ],
    }
    PREFIX_MAP = {
        'employee.': 'hr', 'admin.applications': 'hr',
        'attendance.': 'work', 'payslip.': 'work', 'advance.': 'work',
        'contract.': 'contract',
        'site.': 'ops', 'notice.': 'ops', 'leave.': 'ops',
    }

    ep = req.endpoint or ''
    active_cat = ''
    for cat, endpoints in CATEGORY_MAP.items():
        if ep in endpoints:
            active_cat = cat
            break
    if not active_cat:
        for prefix, cat in PREFIX_MAP.items():
            if ep.startswith(prefix):
                active_cat = cat
                break

    return dict(active_cat=active_cat, current_ep=ep)


# ── APScheduler 초기화 (예약발송 등) ──
from services.scheduler_service import init_scheduler
init_scheduler(app)


if __name__ == '__main__':
    # Nginx가 SSL을 처리하므로 Flask는 보통 5000 포트에서 실행됩니다
    use_debug = os.environ.get('FLASK_DEBUG', '0') == '1'
    app.run(host='127.0.0.1', port=5000, debug=use_debug)
