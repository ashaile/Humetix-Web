import os
from pathlib import Path

from routes import auth as auth_routes


def _login_as_admin(client):
    with client.session_transaction() as sess:
        sess["is_admin"] = True


def test_change_admin_password_success(client, monkeypatch):
    env_file = Path(__file__).resolve().parent / "tmp_admin_password_success.env"
    env_file.write_text("SECRET_KEY=test\nADMIN_PASSWORD=old_pw\n", encoding="utf-8")

    monkeypatch.setattr("routes.admin.ENV_FILE_PATH", str(env_file))
    monkeypatch.setenv("ADMIN_PASSWORD", "old_pw")
    _login_as_admin(client)

    response = client.post(
        "/admin/change-password",
        data={
            "current_password": "old_pw",
            "new_password": "new_pw_1234",
            "confirm_password": "new_pw_1234",
        },
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    assert os.environ["ADMIN_PASSWORD"] == "new_pw_1234"
    assert "ADMIN_PASSWORD=new_pw_1234" in env_file.read_text(encoding="utf-8")
    env_file.unlink(missing_ok=True)


def test_change_admin_password_rejects_wrong_current_password(client, monkeypatch):
    env_file = Path(__file__).resolve().parent / "tmp_admin_password_fail.env"
    env_file.write_text("ADMIN_PASSWORD=old_pw\n", encoding="utf-8")

    monkeypatch.setattr("routes.admin.ENV_FILE_PATH", str(env_file))
    monkeypatch.setenv("ADMIN_PASSWORD", "old_pw")
    _login_as_admin(client)

    response = client.post(
        "/admin/change-password",
        data={
            "current_password": "wrong_pw",
            "new_password": "new_pw_1234",
            "confirm_password": "new_pw_1234",
        },
    )

    assert response.status_code == 400
    body = response.get_json()
    assert body["success"] is False
    assert os.environ["ADMIN_PASSWORD"] == "old_pw"
    assert "ADMIN_PASSWORD=old_pw" in env_file.read_text(encoding="utf-8")
    env_file.unlink(missing_ok=True)


def test_get_admin_password_prefers_env_file(monkeypatch):
    env_file = Path(__file__).resolve().parent / "tmp_auth_password.env"
    env_file.write_text("ADMIN_PASSWORD=file_pw\n", encoding="utf-8")

    monkeypatch.setattr(auth_routes, "ENV_FILE_PATH", str(env_file))
    monkeypatch.setenv("ADMIN_PASSWORD", "process_pw")

    assert auth_routes._get_admin_password() == "file_pw"
    env_file.unlink(missing_ok=True)
