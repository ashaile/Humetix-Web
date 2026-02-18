import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

class Config:
    """기본 설정 (모든 환경 공통)"""
    SECRET_KEY = os.environ.get('SECRET_KEY')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # 환경변수 DATABASE_URL이 있으면 사용, 없으면 로컬 SQLite
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        f"sqlite:///{os.path.join(BASE_DIR, 'humetix.db')}"
    )
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB 제한 (전체 요청 크기)
    
    # 세션 보안 기본 설정 (오버라이딩 가능)
    SESSION_COOKIE_HTTPONLY = True  # 자바스크립트에서 쿠키 접근 차단 (XSS 방지)
    SESSION_COOKIE_SAMESITE = 'Lax' # CSRF 방지
    PERMANENT_SESSION_LIFETIME = 1800 # 30분 (초 단위)

    # 로깅 설정
    @staticmethod
    def get_logging_config(log_dir):
        return {
            'version': 1,
            'formatters': {
                'default': {
                    'format': '[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
                }
            },
            'handlers': {
                'file': {
                    'class': 'logging.handlers.RotatingFileHandler',
                    'filename': os.path.join(log_dir, 'humetix.log'),
                    'maxBytes': 1024 * 1024 * 10, # 10MB
                    'backupCount': 5,
                    'formatter': 'default',
                    'encoding': 'utf-8'
                },
                'console': {
                    'class': 'logging.StreamHandler',
                    'formatter': 'default'
                }
            },
            'root': {
                'level': 'INFO',
                'handlers': ['file', 'console']
            }
        }

class DevelopmentConfig(Config):
    """개발 환경 설정"""
    DEBUG = True
    SESSION_COOKIE_SECURE = False  # 개발 환경(HTTP)에서는 False

class ProductionConfig(Config):
    """운영 환경 설정"""
    DEBUG = False
    SESSION_COOKIE_SECURE = True   # 운영 환경(HTTPS)에서는 True (쿠키 암호화 전송 강제)
    
    # 운영 환경 필수값 검증
    def __init__(self):
        if not self.SECRET_KEY:
            raise RuntimeError("SECRET_KEY environment variable is not set")
        if not os.environ.get('ADMIN_PASSWORD'):
            raise RuntimeError("ADMIN_PASSWORD environment variable is not set")
        
        # 알림 기능 설정 (필수는 아니지만 설정되어 있으면 사용됨)
        self.SMTP_USER = os.environ.get('SMTP_USER')
        self.SMTP_PASS = os.environ.get('SMTP_PASS')
        self.ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL')
        self.SMS_API_KEY = os.environ.get('SMS_API_KEY')
        self.ADMIN_PHONE = os.environ.get('ADMIN_PHONE')

# 환경 변수에 따라 설정 클래스 선택
config_by_name = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
