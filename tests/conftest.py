import os
import re
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("DATABASE_URL", "sqlite://")  # importing app builds a module-level app; keep it in memory

import app as app_module  # noqa: E402

ADMIN_PASSWORD = "test-password-123"
CSRF_RE = re.compile(r'name="csrf_token" value="([^"]+)"')


@pytest.fixture()
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/test.db")
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", ADMIN_PASSWORD)
    monkeypatch.setenv("SECRET_KEY", "x" * 32)
    application = app_module.create_app()
    application.config["TESTING"] = True
    return application


def csrf(html):
    return CSRF_RE.search(html).group(1)


class Admin:
    """Logged-in test client that keeps a fresh CSRF token."""

    def __init__(self, client):
        self.client = client
        token = csrf(client.get("/login").text)
        response = client.post("/login", data={"username": "admin", "password": ADMIN_PASSWORD, "csrf_token": token})
        assert response.status_code == 302
        self.token = csrf(client.get("/").text)

    def get(self, *args, **kwargs):
        return self.client.get(*args, **kwargs)

    def post(self, url, data=None, **kwargs):
        data = dict(data or {})
        data.setdefault("csrf_token", self.token)
        return self.client.post(url, data=data, **kwargs)


@pytest.fixture()
def admin(app):
    return Admin(app.test_client())
