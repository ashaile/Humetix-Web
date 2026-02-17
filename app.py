import os
from flask import Flask, render_template
from dotenv import load_dotenv
from flask_wtf.csrf import CSRFProtect
from flask_migrate import Migrate
from models import db
from werkzeug.middleware.proxy_fix import ProxyFix

# .env ?뚯씪?먯꽌 ?섍꼍蹂??濡쒕뱶
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, '.env'))

from config import config_by_name

app = Flask(__name__)
# Nginx ?꾨줉???ㅼ뿉??HTTPS 諛??ㅻ뜑 ?뺣낫瑜??щ컮瑜닿쾶 泥섎━?섍린 ?꾪빐 ?곸슜
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# ?섍꼍 ?ㅼ젙 ?곸슜 (湲곕낯媛? production)
env_name = os.environ.get('FLASK_ENV', 'production')
app_config = config_by_name[env_name]()
app.config.from_object(app_config)

# 濡쒓퉭 ?ㅼ젙 ?곸슜
LOG_DIR = os.path.join(BASE_DIR, 'logs')
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

from logging.config import dictConfig
dictConfig(app_config.get_logging_config(LOG_DIR))

# DB ?ㅼ젙? config.py?먯꽌 ?쇨??섍쾶 愿由?(?섍꼍蹂??湲곕낯媛?

# 珥덇린??
db.init_app(app)
migrate = Migrate(app, db)
csrf = CSRFProtect(app)

# uploads ?대뜑 ?앹꽦
UPLOAD_DIR = os.path.join(BASE_DIR, 'uploads')
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

# Blueprint ?깅줉
from routes.auth import auth_bp
from routes.apply import apply_bp
from routes.admin import admin_bp

app.register_blueprint(auth_bp)
app.register_blueprint(apply_bp)
app.register_blueprint(admin_bp)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/privacy')
def privacy():
    return render_template('privacy.html')

@app.route('/health')
def health_check():
    """?쒕쾭 ?곹깭 紐⑤땲?곕쭅 ?붾뱶?ъ씤??""
    try:
        db.session.execute(db.text('SELECT 1'))
        return jsonify({"status": "healthy", "database": "connected"}), 200
    except Exception as e:
        return jsonify({"status": "unhealthy", "database": str(e)}), 503

