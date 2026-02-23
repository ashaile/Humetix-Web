import os
from pathlib import Path

import pytest

# Configure a dedicated SQLite DB for tests before importing the Flask app.
TEST_DB_PATH = Path(__file__).resolve().parent / "pytest_humetix.db"
os.environ["FLASK_ENV"] = "development"
os.environ["SECRET_KEY"] = "test_secret_key"
os.environ["ADMIN_PASSWORD"] = "test_admin_password"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH.as_posix()}"

from app import app as _flask_app, db


@pytest.fixture
def flask_app():
    _flask_app.config["TESTING"] = True
    _flask_app.config["WTF_CSRF_ENABLED"] = False

    with _flask_app.app_context():
        db.session.remove()
        db.drop_all()
        db.create_all()
        yield _flask_app
        db.session.remove()
        db.drop_all()
        db.engine.dispose()


@pytest.fixture
def client(flask_app):
    with flask_app.test_client() as client:
        yield client
