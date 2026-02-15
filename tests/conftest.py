import pytest
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
