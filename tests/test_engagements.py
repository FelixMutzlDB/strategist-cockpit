"""Tests for the engagements API (CRUD operations)."""


def test_list_engagements_empty(client):
    resp = client.get("/api/engagements/")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_create_engagement(client):
    payload = {
        "customer": "Acme Corp",
        "engagement_title": "AI Strategy Workshop",
        "engagement_type": "One-off",
        "status": "Not started",
        "fy": "FY27",
    }
    resp = client.post("/api/engagements/", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["customer"] == "Acme Corp"
    assert data["engagement_type"] == "One-off"
    assert data["id"] > 0

    # Cleanup
    client.delete(f"/api/engagements/{data['id']}")


def test_create_engagement_requires_customer(client):
    payload = {"engagement_title": "Missing Customer"}
    resp = client.post("/api/engagements/", json=payload)
    assert resp.status_code == 422


def test_get_engagement(client):
    create = client.post("/api/engagements/", json={"customer": "GetTest Corp"})
    eng_id = create.json()["id"]

    resp = client.get(f"/api/engagements/{eng_id}")
    assert resp.status_code == 200
    assert resp.json()["customer"] == "GetTest Corp"

    client.delete(f"/api/engagements/{eng_id}")


def test_get_engagement_not_found(client):
    resp = client.get("/api/engagements/99999")
    assert resp.status_code == 404


def test_update_engagement(client):
    create = client.post("/api/engagements/", json={
        "customer": "Update Corp",
        "status": "Not started",
    })
    eng_id = create.json()["id"]

    resp = client.put(f"/api/engagements/{eng_id}", json={
        "status": "Ongoing",
        "engagement_title": "Updated Title",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "Ongoing"
    assert data["engagement_title"] == "Updated Title"
    assert data["customer"] == "Update Corp"

    client.delete(f"/api/engagements/{eng_id}")


def test_update_engagement_not_found(client):
    resp = client.put("/api/engagements/99999", json={"status": "Completed"})
    assert resp.status_code == 404


def test_delete_engagement(client):
    create = client.post("/api/engagements/", json={"customer": "Delete Corp"})
    eng_id = create.json()["id"]

    resp = client.delete(f"/api/engagements/{eng_id}")
    assert resp.status_code == 204

    resp = client.get(f"/api/engagements/{eng_id}")
    assert resp.status_code == 404


def test_delete_engagement_not_found(client):
    resp = client.delete("/api/engagements/99999")
    assert resp.status_code == 404


def test_filter_by_fy(client):
    client.post("/api/engagements/", json={"customer": "FY Filter", "fy": "FY25"})
    client.post("/api/engagements/", json={"customer": "FY Filter 2", "fy": "FY26"})

    resp = client.get("/api/engagements/?fy=FY25")
    assert resp.status_code == 200
    assert all(e["fy"] == "FY25" for e in resp.json())


def test_filter_by_type(client):
    client.post("/api/engagements/", json={"customer": "Type Filter", "engagement_type": "Focus"})

    resp = client.get("/api/engagements/?engagement_type=Focus")
    assert resp.status_code == 200
    assert all(e["engagement_type"] == "Focus" for e in resp.json())


def test_filter_by_customer_partial(client):
    client.post("/api/engagements/", json={"customer": "Deutsche Boerse"})

    resp = client.get("/api/engagements/?customer=boerse")
    assert resp.status_code == 200
    assert any("Boerse" in e["customer"] for e in resp.json())
