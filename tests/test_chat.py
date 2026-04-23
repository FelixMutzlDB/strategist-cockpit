"""Tests for the chat API (Stratego chatbot)."""


def test_chat_basic(client):
    resp = client.post("/api/chat/", json={"message": "hello"})
    assert resp.status_code == 200
    data = resp.json()
    assert "response" in data
    assert "source" in data
    assert data["source"] == "stratego"
    assert len(data["response"]) > 0


def test_chat_greeting(client):
    resp = client.post("/api/chat/", json={"message": "Hi there!"})
    data = resp.json()
    assert "stratego" in data["response"].lower() or "hello" in data["response"].lower()


def test_chat_focus_engagements(client):
    resp = client.post("/api/chat/", json={"message": "Tell me about focus accounts"})
    data = resp.json()
    assert "focus" in data["response"].lower()


def test_chat_canvas_topic(client):
    resp = client.post("/api/chat/", json={"message": "What is the strategist canvas?"})
    data = resp.json()
    assert "canvas" in data["response"].lower()


def test_chat_fiscal_year(client):
    resp = client.post("/api/chat/", json={"message": "How does FY work?"})
    data = resp.json()
    assert "fy" in data["response"].lower() or "fiscal" in data["response"].lower() or "february" in data["response"].lower()


def test_chat_dashboard_topic(client):
    resp = client.post("/api/chat/", json={"message": "Show me the impact dashboard"})
    data = resp.json()
    assert "dashboard" in data["response"].lower() or "impact" in data["response"].lower()


def test_chat_generic_fallback(client):
    resp = client.post("/api/chat/", json={"message": "xyzzy random noise"})
    data = resp.json()
    assert len(data["response"]) > 20


def test_chat_empty_message(client):
    resp = client.post("/api/chat/", json={"message": ""})
    assert resp.status_code == 200


def test_chat_missing_message_field(client):
    resp = client.post("/api/chat/", json={})
    assert resp.status_code == 422
