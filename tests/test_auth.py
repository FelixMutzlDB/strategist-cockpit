"""Tests for the current_user_email() FastAPI dependency (SDR F-TM-1, F-TM-4)."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.backend.auth import current_user_email, is_admin


@pytest.fixture
def app_with_dep():
    """A throwaway FastAPI app exposing the dep at /whoami."""
    app = FastAPI()

    @app.get("/whoami")
    def whoami(user: str = current_user_email_dep()):  # noqa: B008
        return {"user": user}

    return app


def current_user_email_dep():
    # Lazy import shim so we can use the dep as a default value above without
    # FastAPI Depends machinery in tests.
    from fastapi import Depends

    return Depends(current_user_email)


def test_header_present_returns_lowercased_email(app_with_dep):
    client = TestClient(app_with_dep)
    resp = client.get("/whoami", headers={"X-Forwarded-Email": "Alice@Databricks.com"})
    assert resp.status_code == 200
    assert resp.json() == {"user": "alice@databricks.com"}


def test_no_header_dev_fallback(monkeypatch, app_with_dep):
    monkeypatch.delenv("STRICT_AUTH", raising=False)
    monkeypatch.delenv("DEV_USER_EMAIL", raising=False)
    client = TestClient(app_with_dep)
    resp = client.get("/whoami")
    assert resp.status_code == 200
    assert resp.json() == {"user": "dev@local"}


def test_no_header_dev_fallback_overridable(monkeypatch, app_with_dep):
    monkeypatch.delenv("STRICT_AUTH", raising=False)
    monkeypatch.setenv("DEV_USER_EMAIL", "tester@example.com")
    client = TestClient(app_with_dep)
    resp = client.get("/whoami")
    assert resp.json() == {"user": "tester@example.com"}


def test_no_header_strict_auth_returns_401(monkeypatch, app_with_dep):
    monkeypatch.setenv("STRICT_AUTH", "1")
    client = TestClient(app_with_dep)
    resp = client.get("/whoami")
    assert resp.status_code == 401
    assert "X-Forwarded-Email" in resp.json()["detail"]


def test_admin_list_default(monkeypatch):
    monkeypatch.delenv("ADMIN_EMAILS", raising=False)
    assert is_admin("felix.mutzl@databricks.com")
    assert is_admin("MARCO.METTING@databricks.com")  # case-insensitive
    assert not is_admin("random@databricks.com")


def test_admin_list_override(monkeypatch):
    monkeypatch.setenv("ADMIN_EMAILS", "ops@x.com,sec@x.com")
    assert is_admin("ops@x.com")
    assert is_admin("sec@x.com")
    assert not is_admin("felix.mutzl@databricks.com")
