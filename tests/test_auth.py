"""Tests for the current_user_email() / current_user_token() FastAPI deps
(SDR F-TM-1, F-TM-4 + T-205 / F-TM-2 + N-11 strict-token consolidation)."""

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from src.backend.auth import current_user_email, current_user_token, is_admin


@pytest.fixture
def app_with_dep():
    """A throwaway FastAPI app exposing the deps at /whoami and /token."""
    app = FastAPI()

    @app.get("/whoami")
    def whoami(user: str = Depends(current_user_email)):
        return {"user": user}

    @app.get("/token")
    def token(tok: str = Depends(current_user_token)):
        return {"token": tok}

    return app


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


# --- current_user_token() tests (T-205 / F-TM-2) ---


def test_token_header_returned_unchanged(app_with_dep):
    client = TestClient(app_with_dep)
    resp = client.get(
        "/token", headers={"X-Forwarded-Access-Token": "OBO-token-from-apps"}
    )
    assert resp.status_code == 200
    assert resp.json() == {"token": "OBO-token-from-apps"}


def test_token_no_header_dev_fallback(monkeypatch, app_with_dep):
    monkeypatch.delenv("STRICT_AUTH", raising=False)
    monkeypatch.setenv("DATABRICKS_TOKEN", "local-pat")
    # Reset the one-shot warning latch so the fallback path is exercised.
    import src.backend.auth as auth_mod

    auth_mod._DEV_TOKEN_FALLBACK_LOGGED = False
    client = TestClient(app_with_dep)
    resp = client.get("/token")
    assert resp.status_code == 200
    assert resp.json() == {"token": "local-pat"}


def test_token_no_header_strict_returns_401(monkeypatch, app_with_dep):
    monkeypatch.setenv("STRICT_AUTH", "1")
    client = TestClient(app_with_dep)
    resp = client.get("/token")
    assert resp.status_code == 401
    assert "X-Forwarded-Access-Token" in resp.json()["detail"]


def test_token_no_header_no_dev_token_returns_401(monkeypatch, app_with_dep):
    monkeypatch.delenv("STRICT_AUTH", raising=False)
    monkeypatch.setenv("DATABRICKS_TOKEN", "")
    client = TestClient(app_with_dep)
    resp = client.get("/token")
    assert resp.status_code == 401
    assert "DATABRICKS_TOKEN" in resp.json()["detail"]
