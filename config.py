import os

class Config:
    """기본 설정 (모든 환경 공통)"""
    SECRET_KEY = os.environ.get('SECRET_KEY')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB 제한 (전체 요청 크기)
    
    # 세션 보안 기본 설정 (오버라이딩 가능)
    SESSION_COOKIE_HTTPONLY = True  # 자바스크립트에서 쿠키 접근 차단 (XSS 방지)
    SESSION_COOKIE_SAMESITE = 'Lax' # CSRF 방지

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

# 환경 변수에 따라 설정 클래스 선택
config_by_name = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
