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

    # ── 급여/근태 정책 (한국 노동법 기준 2026) ──
    HOURLY_WAGE = 10_320                 # 2026년 최저시급 (원)
    MONTHLY_STANDARD_HOURS = 209         # 월 소정근로시간 (주휴수당 포함)
    BASE_SALARY = HOURLY_WAGE * MONTHLY_STANDARD_HOURS  # 2,156,880원
    SALARY_MODE = 'standard'             # 'standard'=209h 고정 | 'actual'=실근무시간
    STANDARD_WORK_HOURS = 8.0            # 1일 기본 근무시간
    BREAK_HOURS = 1.0                    # 휴게시간 (식사) - 주간/야간 동일
    OT_MULTIPLIER = 1.5                  # 잔업/특근 배율
    NIGHT_PREMIUM = 0.5                  # 심야 가산 배율 (22:00~06:00)
    NIGHT_START = 22                     # 심야 시작시
    NIGHT_END = 6                        # 심야 종료시
    TAX_RATE = 0.033                     # 소득세 3.3%
    INSURANCE_RATE = 0.097               # 4대보험 합산 9.7%
    MAX_ADVANCE_PERCENT = 50             # 가불 한도 (기본급 대비 %)
    
    # 가불 유형별 한도 (원)
    ADVANCE_LIMIT_WEEKLY = 300_000       # 주간 근무자
    ADVANCE_LIMIT_SHIFT = 500_000        # 교대 근무자
    
    # 2026년 공휴일 (양력 기준)
    PUBLIC_HOLIDAYS_2026 = [
        '2026-01-01', # 신정
        '2026-02-17', '2026-02-18', '2026-02-19', # 설날 (대체휴일 포함 여부 확인 필요, 우선 기본 연휴)
        '2026-03-01', # 삼일절
        '2026-03-02', # 삼일절 대체공휴일 (예상)
        '2026-05-05', # 어린이날
        '2026-05-24', # 부처님오신날
        '2026-05-25', # 부처님오신날 대체공휴일 (예상)
        '2026-06-06', # 현충일
        '2026-08-15', # 광복절
        '2026-09-24', '2026-09-25', '2026-09-26', # 추석
        '2026-10-03', # 개천절
        '2026-10-09', # 한글날
        '2026-12-25', # 성탄절
    ]
    
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
