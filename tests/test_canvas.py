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


# --- SDR-4682 N-6: canvas summary tenancy ---


def test_canvas_summary_does_not_leak_other_tenants(client, db_session):
    """Another strategist's engagement matching the keywords must NOT appear
    in this strategist's canvas summary — accounts list, count, and detail
    rows all scoped to the caller's strategist_email."""
    from src.backend.models import Engagement

    other = Engagement(
        customer="Other Strategist Corp",
        engagement_title="CIO Vision and exec board session",  # matches c-level keywords
        strategist_email="other.strategist@databricks.com",
    )
    db_session.add(other)
    db_session.commit()

    resp = client.get("/api/canvas/summary/c-level-vision-setting")
    assert resp.status_code == 200
    data = resp.json()
    assert "Other Strategist Corp" not in data["accounts"]
    assert all(
        e["customer"] != "Other Strategist Corp"
        for e in data["recent_engagements"]
    )

    db_session.delete(other)
    db_session.commit()


def test_canvas_summary_includes_only_callers_engagements(client, db_session):
    """My own matching engagements DO appear; another tenant's don't —
    same keywords, two strategists, only one row in the response."""
    from src.backend.models import Engagement

    mine = Engagement(
        customer="My Corp",
        engagement_title="CIO vision board",
        strategist_email="dev@local",  # matches the test identity
    )
    other = Engagement(
        customer="Their Corp",
        engagement_title="CIO vision board",
        strategist_email="other.strategist@databricks.com",
    )
    db_session.add_all([mine, other])
    db_session.commit()

    resp = client.get("/api/canvas/summary/c-level-vision-setting")
    data = resp.json()
    customers = data["accounts"]
    assert "My Corp" in customers
    assert "Their Corp" not in customers

    db_session.delete(mine)
    db_session.delete(other)
    db_session.commit()
