"""Tests for the engagements API (CRUD + input validation)."""


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

    client.delete(f"/api/engagements/{data['id']}")


def test_create_engagement_requires_customer(client):
    resp = client.post("/api/engagements/", json={"engagement_title": "Missing Customer"})
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


# T-109: tightened validation --------------------------------------------------

def test_reject_invalid_engagement_type(client):
    resp = client.post(
        "/api/engagements/",
        json={"customer": "Bad Type", "engagement_type": "NotAType"},
    )
    assert resp.status_code == 422


def test_reject_invalid_status(client):
    resp = client.post(
        "/api/engagements/",
        json={"customer": "Bad Status", "status": "made up"},
    )
    assert resp.status_code == 422


def test_reject_invalid_fy_format(client):
    resp = client.post(
        "/api/engagements/",
        json={"customer": "Bad FY", "fy": "2027"},
    )
    assert resp.status_code == 422


def test_reject_non_url_asq_url(client):
    resp = client.post(
        "/api/engagements/",
        json={"customer": "Bad URL", "asq_url": "not a url"},
    )
    assert resp.status_code == 422


def test_accept_valid_asq_url(client):
    resp = client.post(
        "/api/engagements/",
        json={
            "customer": "Good URL Corp",
            "asq_url": "https://salesforce.com/asq/ASQ-123",
        },
    )
    assert resp.status_code == 201
    client.delete(f"/api/engagements/{resp.json()['id']}")


def test_reject_oversize_customer(client):
    resp = client.post("/api/engagements/", json={"customer": "x" * 2000})
    assert resp.status_code == 422


def test_strips_whitespace_from_inputs(client):
    resp = client.post("/api/engagements/", json={"customer": "  Trimmed Corp  "})
    assert resp.status_code == 201
    data = resp.json()
    assert data["customer"] == "Trimmed Corp"
    client.delete(f"/api/engagements/{data['id']}")


# T-204: UCO IDs field round-trips ---------------------------------------------

def test_engagement_accepts_uco_ids(client):
    resp = client.post(
        "/api/engagements/",
        json={"customer": "UCO Corp", "uco_ids": "UCO-1234, UCO-5678"},
    )
    assert resp.status_code == 201
    eng_id = resp.json()["id"]
    fetched = client.get(f"/api/engagements/{eng_id}").json()
    assert fetched["uco_ids"] == "UCO-1234, UCO-5678"
    client.delete(f"/api/engagements/{eng_id}")


# --- F-TM-1 / SDR-4682 tenancy on the SQLite path ----------------------------


def test_engagement_create_stamps_strategist_email(client):
    """The router must stamp strategist_email from current_user_email — never
    trust a payload field. Default test identity is dev@local."""
    resp = client.post(
        "/api/engagements/",
        json={
            "customer": "Spoof Test",
            # Try to spoof — must be ignored.
            "strategist_email": "evil@elsewhere.com",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["strategist_email"] == "dev@local"
    client.delete(f"/api/engagements/{body['id']}")


def test_engagement_list_filters_by_strategist_email(client, db_session):
    """A row owned by another strategist must not appear in the caller's list."""
    from src.backend.models import Engagement

    # Insert a row owned by someone else, then list as default test user.
    other = Engagement(
        customer="Other Strategist Corp",
        strategist_email="other.strategist@databricks.com",
    )
    db_session.add(other)
    db_session.commit()

    resp = client.get("/api/engagements/")
    customers = [e["customer"] for e in resp.json()]
    assert "Other Strategist Corp" not in customers

    db_session.delete(other)
    db_session.commit()


def test_engagement_get_returns_404_for_other_tenant(client, db_session):
    from src.backend.models import Engagement

    other = Engagement(
        customer="Their Corp",
        strategist_email="other.strategist@databricks.com",
    )
    db_session.add(other)
    db_session.commit()
    other_id = other.id

    resp = client.get(f"/api/engagements/{other_id}")
    assert resp.status_code == 404

    db_session.delete(other)
    db_session.commit()


def test_engagement_update_blocks_other_tenant(client, db_session):
    """Update of another tenant's row must return 404 (not leak existence)."""
    from src.backend.models import Engagement

    other = Engagement(
        customer="Their Corp",
        strategist_email="other.strategist@databricks.com",
    )
    db_session.add(other)
    db_session.commit()
    other_id = other.id

    resp = client.put(
        f"/api/engagements/{other_id}",
        json={"status": "Completed"},
    )
    assert resp.status_code == 404

    db_session.delete(other)
    db_session.commit()


def test_engagement_delete_blocks_other_tenant(client, db_session):
    from src.backend.models import Engagement

    other = Engagement(
        customer="Their Corp",
        strategist_email="other.strategist@databricks.com",
    )
    db_session.add(other)
    db_session.commit()
    other_id = other.id

    resp = client.delete(f"/api/engagements/{other_id}")
    assert resp.status_code == 404

    # Row still exists.
    still_there = (
        db_session.query(Engagement).filter(Engagement.id == other_id).first()
    )
    assert still_there is not None

    db_session.delete(other)
    db_session.commit()


def test_engagement_update_does_not_let_payload_change_strategist_email(client, db_session):
    """Even on a row I own, my Update payload cannot re-stamp the tenant key."""

    create = client.post("/api/engagements/", json={"customer": "Mine Corp"})
    eng_id = create.json()["id"]

    resp = client.put(
        f"/api/engagements/{eng_id}",
        json={"strategist_email": "evil@elsewhere.com", "status": "Ongoing"},
    )
    assert resp.status_code == 200
    assert resp.json()["strategist_email"] == "dev@local"

    client.delete(f"/api/engagements/{eng_id}")
