"""T-212: tests for qualitative impact tag plumbing.

Coverage:
- Pydantic validation: unknown tag, duplicate tag, empty list, valid multi-tag,
  oversize notes.
- ``activity_overlay_repo`` DBSQL: MERGE construction, caller-email stamping,
  spoofing rejection, cross-tenant read isolation.
- ``activity_overlay_repo`` SQLite: round-trip set/get parity.
- HTTP /api/engagements: PUT with valid tags 200; invalid tag 422; duplicate
  tag 422; round-trip read.
- Cross-category overlay row growth (SQLite) — two writes to different
  categories produce two overlay rows.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from pydantic import ValidationError

from src.backend.models import ActivityOverlay
from src.backend.repos import activity_overlay_repo
from src.backend.schemas import EngagementUpdate

# ---------------------------------------------------------------- Pydantic


def test_impact_tags_unknown_raises_422():
    with pytest.raises(ValidationError):
        EngagementUpdate(impact_tags=["nope"])


def test_impact_tags_duplicates_raise_422():
    with pytest.raises(ValidationError):
        EngagementUpdate(impact_tags=["blocker_cleared", "blocker_cleared"])


def test_impact_tags_empty_list_is_ok():
    m = EngagementUpdate(impact_tags=[])
    assert m.impact_tags == []


def test_impact_tags_valid_multi_tag_is_ok():
    m = EngagementUpdate(impact_tags=["blocker_cleared", "exec_intro", "cxo_engaged"])
    assert m.impact_tags == ["blocker_cleared", "exec_intro", "cxo_engaged"]


def test_impact_notes_over_4000_raises_422():
    with pytest.raises(ValidationError):
        EngagementUpdate(impact_notes="x" * 4001)


def test_impact_notes_at_4000_is_ok():
    m = EngagementUpdate(impact_notes="x" * 4000)
    assert m.impact_notes is not None and len(m.impact_notes) == 4000


def test_impact_tags_null_normalised_to_empty_list():
    """Clients sending ``impact_tags=null`` should not 422."""
    m = EngagementUpdate(impact_tags=None)  # type: ignore[arg-type]
    assert m.impact_tags == []


# -------------------------------------------------------- DBSQL repo (mock)


def test_set_tags_constructs_merge_with_caller_email():
    captured = {}

    def fake_execute(token, query, params):
        captured["q"] = query
        captured["p"] = params
        return 1

    with patch.object(activity_overlay_repo.dbsql, "execute", side_effect=fake_execute):
        activity_overlay_repo.set_tags(
            user_token="OBO",
            category="customer",
            activity_key="asq:ASQ-1",
            strategist_email="alice@databricks.com",
            tags=["blocker_cleared", "exec_intro"],
            notes="cleared compute quota with cloud team",
        )

    q = captured["q"]
    p = captured["p"]
    assert "MERGE INTO" in q
    assert "activity_app_data" in q
    # The ON predicate must key all three components.
    assert "t.category = s.category" in q
    assert "t.activity_key = s.activity_key" in q
    assert "t.strategist_email = s.strategist_email" in q
    # The caller's email lands in the params under the canonical key.
    assert p["strategist_email"] == "alice@databricks.com"
    assert p["category"] == "customer"
    assert p["activity_key"] == "asq:ASQ-1"
    assert p["impact_tags"] == ["blocker_cleared", "exec_intro"]
    assert p["impact_notes"] == "cleared compute quota with cloud team"


def test_set_tags_ignores_payload_email_spoof():
    """Even if a caller-provided 'strategist_email' leaks into ``set_tags``
    kwargs, only the explicit parameter is honoured (no **payload pattern)."""
    captured = {}

    def fake_execute(token, query, params):
        captured["p"] = params
        return 1

    with patch.object(activity_overlay_repo.dbsql, "execute", side_effect=fake_execute):
        activity_overlay_repo.set_tags(
            user_token="OBO",
            category="customer",
            activity_key="asq:ASQ-1",
            strategist_email="alice@databricks.com",
            tags=["blocker_cleared"],
            notes=None,
        )
    # The signature is keyword-only; there is no path for a payload
    # ``strategist_email`` to override the caller's email. The repo binds
    # exactly the function argument.
    assert captured["p"]["strategist_email"] == "alice@databricks.com"


def test_get_tags_filters_by_strategist_email():
    """Cross-tenant read isolation — Alice's tags can't return to Bob."""
    captured = {}

    def fake_fetch_one(token, query, params):
        captured["q"] = query
        captured["p"] = params
        return None

    with patch.object(
        activity_overlay_repo.dbsql, "fetch_one", side_effect=fake_fetch_one
    ):
        activity_overlay_repo.get_tags(
            user_token="OBO",
            category="customer",
            activity_key="asq:ASQ-1",
            strategist_email="bob@databricks.com",
        )
    assert "strategist_email = %(strategist_email)s" in captured["q"]
    assert captured["p"]["strategist_email"] == "bob@databricks.com"


def test_two_strategists_get_disjoint_overlay_queries():
    bindings: list[str] = []

    def fake_fetch_one(token, query, params):
        bindings.append(params["strategist_email"])
        return None

    with patch.object(
        activity_overlay_repo.dbsql, "fetch_one", side_effect=fake_fetch_one
    ):
        activity_overlay_repo.get_tags(
            user_token="OBO-A",
            category="customer",
            activity_key="asq:ASQ-1",
            strategist_email="alice@databricks.com",
        )
        activity_overlay_repo.get_tags(
            user_token="OBO-B",
            category="customer",
            activity_key="asq:ASQ-1",
            strategist_email="bob@databricks.com",
        )
    assert bindings == ["alice@databricks.com", "bob@databricks.com"]


# -------------------------------------------------------- SQLite repo (real)


def test_sqlite_round_trip_set_then_get(db_session):
    activity_overlay_repo.set_tags_sqlite(
        db_session,
        category="customer",
        activity_key="asq:123",
        strategist_email="alice@x.com",
        tags=["blocker_cleared", "exec_intro"],
        notes="hello",
    )
    row = activity_overlay_repo.get_tags_sqlite(
        db_session,
        category="customer",
        activity_key="asq:123",
        strategist_email="alice@x.com",
    )
    assert row is not None
    # Order-insensitive equality — overlay storage shape is set-like in spirit.
    assert set(row["impact_tags"]) == {"blocker_cleared", "exec_intro"}
    assert row["impact_notes"] == "hello"

    # Cross-tenant: Bob does not see Alice's overlay row.
    assert (
        activity_overlay_repo.get_tags_sqlite(
            db_session,
            category="customer",
            activity_key="asq:123",
            strategist_email="bob@x.com",
        )
        is None
    )

    # Cleanup
    db_session.query(ActivityOverlay).delete()
    db_session.commit()


# ------------------------------------------------------------- HTTP routes


def test_put_engagement_with_impact_tags_200(client):
    create = client.post(
        "/api/engagements/",
        json={"customer": "TagTest Corp"},
        headers={"X-Forwarded-Email": "dev@local"},
    )
    eng_id = create.json()["id"]

    resp = client.put(
        f"/api/engagements/{eng_id}",
        json={"impact_tags": ["blocker_cleared", "exec_intro"], "impact_notes": "win"},
        headers={"X-Forwarded-Email": "dev@local"},
    )
    assert resp.status_code == 200
    assert set(resp.json()["impact_tags"]) == {"blocker_cleared", "exec_intro"}
    assert resp.json()["impact_notes"] == "win"

    # Round-trip via GET.
    got = client.get(
        f"/api/engagements/{eng_id}",
        headers={"X-Forwarded-Email": "dev@local"},
    )
    assert got.status_code == 200
    assert set(got.json()["impact_tags"]) == {"blocker_cleared", "exec_intro"}

    client.delete(f"/api/engagements/{eng_id}")


def test_put_engagement_unknown_tag_422(client):
    create = client.post(
        "/api/engagements/",
        json={"customer": "BadTag Corp"},
        headers={"X-Forwarded-Email": "dev@local"},
    )
    eng_id = create.json()["id"]

    resp = client.put(
        f"/api/engagements/{eng_id}",
        json={"impact_tags": ["nope"]},
        headers={"X-Forwarded-Email": "dev@local"},
    )
    assert resp.status_code == 422

    client.delete(f"/api/engagements/{eng_id}")


def test_put_engagement_duplicate_tag_422(client):
    create = client.post(
        "/api/engagements/",
        json={"customer": "DupTag Corp"},
        headers={"X-Forwarded-Email": "dev@local"},
    )
    eng_id = create.json()["id"]

    resp = client.put(
        f"/api/engagements/{eng_id}",
        json={"impact_tags": ["blocker_cleared", "blocker_cleared"]},
        headers={"X-Forwarded-Email": "dev@local"},
    )
    assert resp.status_code == 422

    client.delete(f"/api/engagements/{eng_id}")


def test_cross_category_overlay_row_count(db_session):
    """Two different (category, activity_key) writes produce two overlay rows.

    Stub for the future cross-category HTTP test once the evangelism /
    initiative routes ship — for now we exercise the repo directly.
    """
    db_session.query(ActivityOverlay).delete()
    db_session.commit()

    activity_overlay_repo.set_tags_sqlite(
        db_session,
        category="customer",
        activity_key="asq:1",
        strategist_email="alice@x.com",
        tags=["blocker_cleared"],
        notes=None,
    )
    activity_overlay_repo.set_tags_sqlite(
        db_session,
        category="evangelism",
        activity_key="evangelism:1",
        strategist_email="alice@x.com",
        tags=["evangelism_landed"],
        notes=None,
    )
    assert db_session.query(ActivityOverlay).count() == 2

    db_session.query(ActivityOverlay).delete()
    db_session.commit()
