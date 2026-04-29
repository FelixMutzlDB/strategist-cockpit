"""Regression tests for F-TM-3 — path traversal in the SPA catch-all.

The previous custom catch-all in src/backend/main.py joined a user-supplied
path into static_dir without canonicalisation, so a request like
``GET /../app.yaml`` would happily serve files outside static_dir.

The fix replaces the catch-all with Starlette's StaticFiles(html=True), which
resolves the candidate path and rejects anything that escapes the directory.
These tests place a sentinel file outside static_dir and confirm the response
never leaks its contents.
"""

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
SENTINEL_PATH = REPO_ROOT / "do_not_serve_secret.txt"
SENTINEL_TEXT = "TRAVERSAL_SENTINEL_DO_NOT_SERVE"


@pytest.fixture(scope="module", autouse=True)
def sentinel_file():
    """Drop a sentinel file at the repo root to attempt to leak via traversal."""
    SENTINEL_PATH.write_text(SENTINEL_TEXT)
    yield
    SENTINEL_PATH.unlink(missing_ok=True)


@pytest.mark.parametrize(
    "path",
    [
        "/../do_not_serve_secret.txt",
        "/..%2fdo_not_serve_secret.txt",
        "/../../do_not_serve_secret.txt",
        "/foo/../../do_not_serve_secret.txt",
    ],
)
def test_traversal_does_not_leak_sentinel(client, path):
    resp = client.get(path)
    # Whether the framework returns 404 or falls back to index.html, the
    # response body must NOT contain the sentinel.
    assert SENTINEL_TEXT not in resp.text, (
        f"path traversal via {path!r} leaked sentinel — got status {resp.status_code}"
    )


def test_root_serves_spa_index(client):
    resp = client.get("/")
    assert resp.status_code == 200
    # Either our test stub or a built index.html — both contain "html".
    assert "<html" in resp.text.lower()


def test_api_route_still_returns_json(client):
    """Mount order: /api/* routes are registered first and must win over the
    StaticFiles mount at /."""
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
