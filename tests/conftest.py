"""Shared test fixtures for the Strategist Cockpit test suite."""

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ["DATABASE_URL"] = "sqlite:///test_strategist.db"
# Provide a benign dev fallback so current_user_token() doesn't 401 in tests
# that don't explicitly inject X-Forwarded-Access-Token. Tests that exercise
# strict-auth/401 paths use monkeypatch.setenv("STRICT_AUTH", "1") + delenv
# to override.
os.environ.setdefault("DATABRICKS_TOKEN", "test-fallback-token")

# Ensure a minimal static/ directory exists at the path main.py expects so the
# SPA mount is registered when tests import the app. CI's frontend job builds
# the real static/ in another step; the backend job and local pytest don't, so
# we stub it. This is the only mechanism a test has to exercise the SPA mount
# (e.g. tests/test_static_traversal.py).
_STATIC_DIR = Path(__file__).parent.parent / "static"
if not _STATIC_DIR.exists():
    _STATIC_DIR.mkdir(parents=True)
    (_STATIC_DIR / "index.html").write_text(
        "<!DOCTYPE html><html><body>test SPA</body></html>"
    )

from src.backend.database import Base, get_db  # noqa: E402
from src.backend.main import app  # noqa: E402
from src.backend.models import Engagement, Project  # noqa: E402


@pytest.fixture(scope="session")
def engine():
    eng = create_engine("sqlite:///test_strategist.db", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=eng)
    yield eng
    Base.metadata.drop_all(bind=eng)
    os.remove("test_strategist.db") if os.path.exists("test_strategist.db") else None


@pytest.fixture
def db_session(engine):
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.rollback()
    session.close()


@pytest.fixture
def client(engine):
    Session = sessionmaker(bind=engine)

    def _get_test_db():
        session = Session()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = _get_test_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def sample_engagement(db_session) -> Engagement:
    eng = Engagement(
        customer="Test Corp",
        engagement_title="Data Platform Strategy",
        engagement_type="Focus",
        status="Ongoing",
        fy="FY26",
        quarter="FY26Q1",
        ae="Jane Doe",
        asq_id="ASQ-001",
        # F-TM-1: stamp tenant so list/get/canvas endpoints find this row
        # under the dev fallback identity used by tests.
        strategist_email="dev@local",
    )
    db_session.add(eng)
    db_session.commit()
    db_session.refresh(eng)
    yield eng
    db_session.delete(eng)
    db_session.commit()


@pytest.fixture
def sample_project(db_session) -> Project:
    proj = Project(
        name="Test Project",
        url="https://example.com",
        description="A test project",
        category="Presentation",
    )
    db_session.add(proj)
    db_session.commit()
    db_session.refresh(proj)
    yield proj
    db_session.delete(proj)
    db_session.commit()
