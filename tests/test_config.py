"""Tests for /api/config (T-201 / T-202)."""

from __future__ import annotations


def test_config_returns_defaults(client):
    resp = client.get("/api/config/")
    assert resp.status_code == 200
    data = resp.json()
    # All fields present, defaults are empty strings (set via env in prod).
    assert {
        "databricks_host",
        "lakeview_dashboard_id",
        "genie_space_id",
        "data_backend",
    } == set(data.keys())


def test_config_reflects_env_settings(client, monkeypatch):
    from src.backend.config import settings

    monkeypatch.setattr(settings, "databricks_host", "adb-test.databricks.net")
    monkeypatch.setattr(settings, "lakeview_dashboard_id", "abc-dashboard-id")
    monkeypatch.setattr(settings, "genie_space_id", "xyz-genie-id")
    resp = client.get("/api/config/")
    body = resp.json()
    assert body["databricks_host"] == "adb-test.databricks.net"
    assert body["lakeview_dashboard_id"] == "abc-dashboard-id"
    assert body["genie_space_id"] == "xyz-genie-id"


def test_config_does_not_require_auth(client):
    """No X-Forwarded-Email needed — the SPA hits this before login."""
    resp = client.get("/api/config/")
    assert resp.status_code == 200
