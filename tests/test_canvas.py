"""Tests for the canvas summary API."""

import pytest


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


# T-104: duplicate positions on the canvas now have unique slugs; each one
# must resolve to the same keyword-based matches as the canonical slug.
@pytest.mark.parametrize(
    "slug,canonical",
    [
        ("events-customer", "events"),
        ("events-evangelism", "events"),
        ("market-scouting-customer", "market-scouting"),
        ("market-scouting-evangelism", "market-scouting"),
        ("community-seeding-evangelism", "community-seeding"),
        ("community-seeding-thought-leadership", "community-seeding"),
    ],
)
def test_canvas_deduped_slugs_match_canonical(client, slug, canonical):
    # Seed an engagement whose title picks up the keyword set.
    client.post("/api/engagements/", json={
        "customer": f"Slug Corp {slug}",
        "engagement_title": "DAIS conference keynote and community event",
    })

    a = client.get(f"/api/canvas/summary/{slug}").json()
    b = client.get(f"/api/canvas/summary/{canonical}").json()
    # Counts and account sets should match since they share keyword lists.
    assert a["engagement_count"] == b["engagement_count"]
    assert sorted(a["accounts"]) == sorted(b["accounts"])
