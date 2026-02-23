import os
from datetime import timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'humetix.db')}"
    )
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024

    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 1800,
        "pool_size": 5,
        "max_overflow": 10,
    }

    HOURLY_WAGE = 10_320
    MONTHLY_STANDARD_HOURS = 209
    BASE_SALARY = HOURLY_WAGE * MONTHLY_STANDARD_HOURS
    SALARY_MODE = "standard"
    STANDARD_WORK_HOURS = 8.0
    BREAK_HOURS = 1.0
    OT_MULTIPLIER = 1.5
    NIGHT_PREMIUM = 0.5
    NIGHT_START = 22
    NIGHT_END = 6
    TAX_RATE = 0.033
    INSURANCE_RATE = 0.097
    MAX_ADVANCE_PERCENT = 50

    ADVANCE_LIMIT_WEEKLY = 300_000
    ADVANCE_LIMIT_SHIFT = 500_000

    LOGIN_MAX_ATTEMPTS = 5
    LOGIN_BLOCK_SECONDS = 300

    PUBLIC_HOLIDAYS_2026 = [
        "2026-01-01",
        "2026-02-17",
        "2026-02-18",
        "2026-03-01",
        "2026-03-02",
        "2026-05-05",
        "2026-05-24",
        "2026-05-25",
        "2026-06-06",
        "2026-08-15",
        "2026-09-24",
        "2026-09-25",
        "2026-09-26",
        "2026-10-03",
        "2026-10-09",
        "2026-12-25",
    ]

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = _env_bool("SESSION_COOKIE_SECURE", False)
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=30)
    WTF_CSRF_TIME_LIMIT = 7200

    @staticmethod
    def get_logging_config(log_dir):
        return {
            "version": 1,
            "formatters": {
                "default": {
                    "format": "[%(asctime)s] %(levelname)s in %(module)s: %(message)s",
                }
            },
            "handlers": {
                "file": {
                    "class": "logging.handlers.RotatingFileHandler",
                    "filename": os.path.join(log_dir, "humetix.log"),
                    "maxBytes": 1024 * 1024 * 10,
                    "backupCount": 5,
                    "formatter": "default",
                    "encoding": "utf-8",
                },
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                },
            },
            "root": {
                "level": "INFO",
                "handlers": ["file", "console"],
            },
        }


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False

    def __init__(self):
        self.SESSION_COOKIE_SECURE = _env_bool("SESSION_COOKIE_SECURE", True)
        if not self.SECRET_KEY:
            raise RuntimeError("SECRET_KEY environment variable is not set")
        if not os.environ.get("ADMIN_PASSWORD"):
            raise RuntimeError("ADMIN_PASSWORD environment variable is not set")

        self.SMTP_USER = os.environ.get("SMTP_USER")
        self.SMTP_PASS = os.environ.get("SMTP_PASS")
        self.ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL")
        self.SMS_API_KEY = os.environ.get("SMS_API_KEY")
        self.ADMIN_PHONE = os.environ.get("ADMIN_PHONE")


config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}
