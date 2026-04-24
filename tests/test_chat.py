"""Tests for the chat API (Stratego chatbot).

With the keyword ladder removed, the router is a thin proxy to the KA serving
endpoint plus a single offline response when the endpoint isn't configured.
Tests run without Databricks credentials, so they exercise the offline path.
"""

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
