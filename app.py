import os
from flask import Flask, render_template
from dotenv import load_dotenv
from flask_wtf.csrf import CSRFProtect
from models import db

# .env 파일에서 환경변수 로드
load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'fallback_dev_key_change_me')

# DB 설정
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(BASE_DIR, 'humetix.db')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# 초기화
db.init_app(app)
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

# DB 테이블 자동 생성
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    # Nginx가 SSL을 처리하므로, Flask는 항상 5000번 포트에서 실행합니다.
    app.run(host='0.0.0.0', port=5000, debug=False)