import os
from flask import Flask, render_template
from dotenv import load_dotenv
from flask_wtf.csrf import CSRFProtect
from flask_migrate import Migrate
from models import db

# .env 파일에서 환경변수 로드
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, '.env'))

from config import config_by_name

app = Flask(__name__)

# 환경 설정 적용 (기본값: production)
env_name = os.environ.get('FLASK_ENV', 'production')
app_config = config_by_name[env_name]()
app.config.from_object(app_config)

# 로깅 설정 적용
LOG_DIR = os.path.join(BASE_DIR, 'logs')
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

from logging.config import dictConfig
dictConfig(app_config.get_logging_config(LOG_DIR))

# DB 설정 (config.py로 이동하지 않은 동적 경로 설정 등은 유지 가능하나, 여기서는 URI도 config로 뺄 수 있음. 
# 현재 구조 유지를 위해 DB URI는 유지하되, 나머지는 Config에서 처리됨)
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(BASE_DIR, 'humetix.db')}"

# 초기화
db.init_app(app)
migrate = Migrate(app, db)
csrf = CSRFProtect(app)

# uploads 폴더 생성
UPLOAD_DIR = os.path.join(BASE_DIR, 'uploads')
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

# Blueprint 등록
from routes.auth import auth_bp
from routes.apply import apply_bp
from routes.admin import admin_bp

app.register_blueprint(auth_bp)
app.register_blueprint(apply_bp)
app.register_blueprint(admin_bp)

@app.route('/')
def index():
    return render_template('index.html')



@app.errorhandler(404)
def page_not_found(e):
    return render_template('error.html', error_code="404", error_message="페이지를 찾을 수 없습니다", error_description="요청하신 페이지가 존재하지 않거나 주소가 변경되었습니다."), 404

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('error.html', error_code="500", error_message="서버 내부 오류", error_description="잠시 후 다시 시도해주세요. 문제가 지속되면 관리자에게 문의 바랍니다."), 500

if __name__ == '__main__':
    # Nginx가 SSL을 처리하므로, Flask는 항상 5000번 포트에서 실행합니다.
    app.run(host='0.0.0.0', port=5000, debug=False)