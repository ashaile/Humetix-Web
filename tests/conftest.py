import os
import pytest

# 테스트 실행 시 환경변수 강제 설정 (app import 전에 수행해야 함)
os.environ['FLASK_ENV'] = 'development'
os.environ['SECRET_KEY'] = 'test_secret_key'
os.environ['ADMIN_PASSWORD'] = 'test_admin_password'

from app import app, db
from models import Application

@pytest.fixture
def client():
    # 테스트용 설정
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:' # 인메모리 DB
    app.config['WTF_CSRF_ENABLED'] = False # 테스트 편의를 위해 CSRF 비활성화

    with app.test_client() as client:
        with app.app_context():
            db.create_all()
            yield client
            db.session.remove()
            db.drop_all()
