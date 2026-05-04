"""Tests for the security response-header middleware."""

import pytest


@pytest.fixture
def health_response(client):
    return client.get("/api/health")


def test_health_ok(health_response):
    assert health_response.status_code == 200


def test_x_content_type_options(health_response):
    assert health_response.headers.get("X-Content-Type-Options") == "nosniff"


def test_x_frame_options(health_response):
    assert health_response.headers.get("X-Frame-Options") == "SAMEORIGIN"


def test_referrer_policy(health_response):
    assert (
        health_response.headers.get("Referrer-Policy")
        == "strict-origin-when-cross-origin"
    )


def test_permissions_policy(health_response):
    value = health_response.headers.get("Permissions-Policy", "")
    for directive in ("camera=()", "microphone=()", "geolocation=()"):
        assert directive in value


def test_content_security_policy_present(health_response):
    csp = health_response.headers.get("Content-Security-Policy", "")
    # Non-empty and pins the defaults we care about.
    assert csp, "CSP header must be set"
    assert "default-src 'self'" in csp
    assert "object-src 'none'" in csp
    assert "base-uri 'self'" in csp
    assert "frame-ancestors 'self'" in csp


def test_csp_frame_src_locked_down_by_default(health_response):
    csp = health_response.headers.get("Content-Security-Policy", "")
    # Default: no frame sources allowed until env vars opt in (dashboard / Genie embed).
    assert "frame-src 'none'" in csp


def test_no_cors_headers(health_response):
    # We removed CORSMiddleware — a plain GET should not produce these.
    assert "Access-Control-Allow-Origin" not in health_response.headers
    assert "Access-Control-Allow-Credentials" not in health_response.headers


def test_csp_frame_src_picks_up_workspace_host_when_configured(client, monkeypatch):
    """T-201/T-202: when CSP_FRAME_SRC is set to the workspace host, the
    Lakeview + Genie iframes must be allowed without `'none'` blocking them."""
    monkeypatch.setenv("CSP_FRAME_SRC", "adb-2548836972759138.18.azuredatabricks.net")
    resp = client.get("/api/health")
    csp = resp.headers.get("Content-Security-Policy", "")
    assert "adb-2548836972759138.18.azuredatabricks.net" in csp
    assert "frame-src 'self' adb-" in csp
    assert "frame-src 'none'" not in csp
