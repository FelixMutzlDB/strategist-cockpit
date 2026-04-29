"""Tests for the projects API (Gallery CRUD + DELETE ownership gating)."""


def test_list_projects(client):
    resp = client.get("/api/projects/")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_create_project(client):
    payload = {
        "name": "Test Presentation",
        "url": "https://docs.google.com/test",
        "description": "A test slide deck",
        "category": "Presentation",
    }
    resp = client.post("/api/projects/", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Test Presentation"
    assert data["url"] == "https://docs.google.com/test"
    assert data["id"] > 0
    # T-208: created_by_email is captured from the (default-fallback) caller.
    assert data["created_by_email"]

    # Cleanup uses the same default identity that created it.
    client.delete(f"/api/projects/{data['id']}")


def test_create_project_requires_name_and_url(client):
    resp = client.post("/api/projects/", json={"description": "No name or url"})
    assert resp.status_code == 422


def test_delete_project_not_found(client):
    resp = client.delete("/api/projects/99999")
    assert resp.status_code == 404


# T-208 / SDR F-TM-5 — DELETE is gated to creator or admin -------------------

ALICE = {"X-Forwarded-Email": "alice@databricks.com"}
BOB = {"X-Forwarded-Email": "bob@databricks.com"}
ADMIN = {"X-Forwarded-Email": "felix.mutzl@databricks.com"}


def test_delete_by_creator_succeeds(client):
    create = client.post(
        "/api/projects/",
        json={"name": "Alice's deck", "url": "https://example.com/a"},
        headers=ALICE,
    )
    pid = create.json()["id"]
    assert create.json()["created_by_email"] == "alice@databricks.com"

    resp = client.delete(f"/api/projects/{pid}", headers=ALICE)
    assert resp.status_code == 204


def test_delete_by_other_user_returns_404(client):
    """Per SDR-4682 F-TM-5: 404 (not 403) so a non-owner can't probe existence."""
    create = client.post(
        "/api/projects/",
        json={"name": "Alice's other deck", "url": "https://example.com/b"},
        headers=ALICE,
    )
    pid = create.json()["id"]

    resp = client.delete(f"/api/projects/{pid}", headers=BOB)
    assert resp.status_code == 404

    # Confirm the project still exists for the rightful owner.
    listing = client.get("/api/projects/").json()
    assert any(p["id"] == pid for p in listing)
    client.delete(f"/api/projects/{pid}", headers=ALICE)


def test_admin_can_delete_anyones_project(client):
    create = client.post(
        "/api/projects/",
        json={"name": "Bob's deck", "url": "https://example.com/c"},
        headers=BOB,
    )
    pid = create.json()["id"]

    resp = client.delete(f"/api/projects/{pid}", headers=ADMIN)
    assert resp.status_code == 204
