"""Tests for the chat API (Stratego chatbot).

With the keyword ladder removed, the router is a thin proxy to the KA serving
endpoint plus a single offline response when the endpoint isn't configured.
Tests run without Databricks credentials, so they exercise the offline path.

T-205: chat now constructs WorkspaceClient with the user's OBO token. Tests
inject ``X-Forwarded-Access-Token`` to exercise the prod path and use
``monkeypatch.setattr`` to swap in a fake SDK so we never hit the network.
"""

from unittest.mock import MagicMock

from src.backend.routers.chat import OFFLINE_RESPONSE


def test_chat_basic(client):
    resp = client.post("/api/chat/", json={"message": "hello"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["source"] == "stratego"
    assert data["response"] == OFFLINE_RESPONSE


def test_chat_non_empty_response(client):
    resp = client.post("/api/chat/", json={"message": "anything"})
    assert len(resp.json()["response"]) > 0


def test_chat_offline_mentions_endpoint_env_var(client):
    resp = client.post("/api/chat/", json={"message": "why offline"})
    assert "STRATEGO_ENDPOINT_NAME" in resp.json()["response"]


def test_chat_empty_message(client):
    resp = client.post("/api/chat/", json={"message": ""})
    assert resp.status_code == 200


def test_chat_missing_message_field(client):
    resp = client.post("/api/chat/", json={})
    assert resp.status_code == 422


def test_chat_rejects_oversized_message(client):
    resp = client.post("/api/chat/", json={"message": "x" * 5000})
    assert resp.status_code == 422


# --- T-205 OBO path -------------------------------------------------------


def test_chat_uses_obo_token_when_endpoint_configured(client, monkeypatch):
    """When STRATEGO_ENDPOINT_NAME is set, WorkspaceClient must be constructed
    with the user's forwarded access token, not the app SP credentials."""
    from src.backend.config import settings

    monkeypatch.setattr(settings, "stratego_endpoint_name", "stratego-ka")
    monkeypatch.setattr(settings, "databricks_host", "adb-test.databricks.net")

    captured: dict = {}

    class FakeChoiceMessage:
        content = "hi from KA"

    class FakeChoice:
        message = FakeChoiceMessage()

    class FakeResponse:
        choices = [FakeChoice()]

    class FakeServingEndpoints:
        def query(self, *, name, messages):
            captured["endpoint"] = name
            captured["messages"] = messages
            return FakeResponse()

    class FakeWorkspaceClient:
        def __init__(self, host=None, token=None):
            captured["host"] = host
            captured["token"] = token
            self.serving_endpoints = FakeServingEndpoints()

    fake_sdk = MagicMock()
    fake_sdk.WorkspaceClient = FakeWorkspaceClient
    monkeypatch.setitem(__import__("sys").modules, "databricks.sdk", fake_sdk)

    resp = client.post(
        "/api/chat/",
        json={"message": "hello"},
        headers={"X-Forwarded-Access-Token": "OBO-token-xyz"},
    )
    assert resp.status_code == 200
    assert resp.json()["response"] == "hi from KA"
    assert captured["token"] == "OBO-token-xyz"
    assert captured["host"] == "adb-test.databricks.net"
    assert captured["endpoint"] == "stratego-ka"


def test_chat_returns_offline_when_obo_call_fails(client, monkeypatch):
    """Network/SDK failures must not leak — return offline response and
    log a warning (already covered by inner try/except)."""
    from src.backend.config import settings

    monkeypatch.setattr(settings, "stratego_endpoint_name", "stratego-ka")

    class BoomWorkspaceClient:
        def __init__(self, *_, **__):
            raise RuntimeError("network down")

    fake_sdk = MagicMock()
    fake_sdk.WorkspaceClient = BoomWorkspaceClient
    monkeypatch.setitem(__import__("sys").modules, "databricks.sdk", fake_sdk)

    resp = client.post(
        "/api/chat/",
        json={"message": "hello"},
        headers={"X-Forwarded-Access-Token": "OBO-token-xyz"},
    )
    assert resp.status_code == 200
    assert resp.json()["response"] == OFFLINE_RESPONSE


def test_chat_strict_auth_rejects_missing_token(client, monkeypatch):
    """In STRICT_AUTH mode (prod), missing OBO header must 401 — never silently
    fall back to a local DATABRICKS_TOKEN."""
    monkeypatch.setenv("STRICT_AUTH", "1")
    resp = client.post(
        "/api/chat/",
        json={"message": "hello"},
        headers={"X-Forwarded-Email": "felix@databricks.com"},
        # No X-Forwarded-Access-Token on purpose
    )
    assert resp.status_code == 401
