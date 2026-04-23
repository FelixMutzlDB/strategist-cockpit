"""Tests for the projects API (Gallery CRUD)."""


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

    client.delete(f"/api/projects/{data['id']}")


def test_create_project_requires_name_and_url(client):
    resp = client.post("/api/projects/", json={"description": "No name or url"})
    assert resp.status_code == 422


def test_delete_project(client):
    create = client.post("/api/projects/", json={
        "name": "To Delete",
        "url": "https://example.com",
    })
    proj_id = create.json()["id"]

    resp = client.delete(f"/api/projects/{proj_id}")
    assert resp.status_code == 204


def test_delete_project_not_found(client):
    resp = client.delete("/api/projects/99999")
    assert resp.status_code == 404
