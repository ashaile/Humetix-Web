import os

class Config:
    """기본 설정 (모든 환경 공통)"""
    SECRET_KEY = os.environ.get('SECRET_KEY')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = 8 * 1024 * 1024  # 8MB 제한 (업로드 5MB + 폼 데이터 마진)

    # DB 설정 (환경변수로 오버라이드 가능)
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URI',
        f"sqlite:///{os.path.join(BASE_DIR, 'humetix.db')}"
    )

    # 세션 보안 기본 설정
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = 1800  # 30분

    # 로깅 설정
    @staticmethod
    def get_logging_config(log_dir):
        return {
            'version': 1,
            'disable_existing_loggers': False,
            'formatters': {
                'default': {
                    'format': '[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
                },
                'json': {
                    'format': '%(asctime)s %(levelname)s %(module)s %(message)s',
                }
            },
            'handlers': {
                'file': {
                    'class': 'logging.handlers.RotatingFileHandler',
                    'filename': os.path.join(log_dir, 'humetix.log'),
                    'maxBytes': 1024 * 1024 * 10,  # 10MB
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
    SESSION_COOKIE_SECURE = False

class ProductionConfig(Config):
    """운영 환경 설정"""
    DEBUG = False
    SESSION_COOKIE_SECURE = True

    def __init__(self):
        if not self.SECRET_KEY:
            raise RuntimeError("SECRET_KEY environment variable is not set")
        if not os.environ.get('ADMIN_PASSWORD'):
            raise RuntimeError("ADMIN_PASSWORD environment variable is not set")

        # 알림 기능 설정
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
