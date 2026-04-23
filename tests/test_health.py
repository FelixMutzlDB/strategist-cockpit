"""Tests for health check and basic app functionality."""


def test_health_endpoint(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["app"] == "strategist-cockpit"


def test_unknown_api_route(client):
    resp = client.get("/api/nonexistent")
    assert resp.status_code in (404, 200)
