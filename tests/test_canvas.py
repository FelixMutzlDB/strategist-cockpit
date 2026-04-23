"""Tests for the canvas summary API."""


def test_canvas_summary_known_activity(client):
    client.post("/api/engagements/", json={
        "customer": "Canvas Test Corp",
        "engagement_title": "Data & AI Strategy Review",
        "engagement_type": "Focus",
        "status": "Completed",
    })

    resp = client.get("/api/canvas/summary/data-ai-strategy")
    assert resp.status_code == 200
    data = resp.json()
    assert data["activity"] == "data-ai-strategy"
    assert isinstance(data["engagement_count"], int)
    assert isinstance(data["accounts"], list)
    assert isinstance(data["recent_engagements"], list)


def test_canvas_summary_unknown_activity(client):
    resp = client.get("/api/canvas/summary/nonexistent-activity")
    assert resp.status_code == 200
    data = resp.json()
    assert data["engagement_count"] == 0
    assert data["accounts"] == []


def test_canvas_summary_keyword_matching(client):
    client.post("/api/engagements/", json={
        "customer": "Keyword Corp",
        "engagement_title": "CIO Vision Workshop",
        "engagement_type": "One-off",
    })

    resp = client.get("/api/canvas/summary/c-level-vision-setting")
    data = resp.json()
    assert data["engagement_count"] >= 1
    assert "Keyword Corp" in data["accounts"]


def test_canvas_summary_limits_recent(client):
    for i in range(8):
        client.post("/api/engagements/", json={
            "customer": f"Bulk Corp {i}",
            "engagement_title": "Vision session with exec board",
        })

    resp = client.get("/api/canvas/summary/c-level-vision-setting")
    data = resp.json()
    assert len(data["recent_engagements"]) <= 5
