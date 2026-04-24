"""Tests for the seed_database helpers (idempotency + quarter normalization)."""

from data.seed_database import normalize_quarter, seed_engagements, seed_projects
from src.backend.models import Engagement


def test_normalize_quarter_plain_form_unchanged():
    assert normalize_quarter("FY26Q1") == "FY26Q1"


def test_normalize_quarter_collapses_dash():
    assert normalize_quarter("FY25-Q1") == "FY25Q1"


def test_normalize_quarter_collapses_in_list():
    assert normalize_quarter("FY25-Q1, FY25Q2") == "FY25Q1, FY25Q2"


def test_normalize_quarter_none_passthrough():
    assert normalize_quarter(None) is None
    assert normalize_quarter("") is None


def test_normalize_quarter_is_case_insensitive_on_fy_prefix():
    assert normalize_quarter("fy25-q1") == "fy25q1"


def test_seed_engagements_idempotent_without_force(db_session, client):
    # Insert a single row via the API, then run the seeder — it should refuse
    # to touch the existing row.
    client.post("/api/engagements/", json={"customer": "Pre-existing Corp"})
    baseline = db_session.query(Engagement).count()

    added = seed_engagements(force=False)

    assert added == 0
    assert db_session.query(Engagement).count() == baseline


def test_seed_projects_idempotent_without_force(db_session):
    from src.backend.models import Project

    db_session.add(Project(name="Pre-existing", url="https://example.com"))
    db_session.commit()
    baseline = db_session.query(Project).count()

    added = seed_projects(force=False)

    assert added == 0
    assert db_session.query(Project).count() == baseline
