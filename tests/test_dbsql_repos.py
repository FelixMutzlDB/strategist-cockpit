"""Tests for the DBSQL data backend (T-206 + F-TM-1).

We don't have a SQL warehouse during pytest, so we patch
``src.backend.dbsql`` and assert on the SQL strings + params constructed
by ``src.backend.repos.*``.

Key assertions:
1. Every SELECT includes ``strategist_email = %(strategist_email)s`` (F-TM-1).
2. INSERTs stamp ``strategist_email`` from the caller, never trust client input.
3. DELETEs filter by both id AND strategist_email so a forged id can't reach
   another tenant's row.
4. Two-strategist test: same router call from two emails produces queries
   parameterised with their own emails — disjoint result sets by construction.
"""

from __future__ import annotations

from unittest.mock import patch

from src.backend.repos import engagements_repo, projects_repo

# --- engagements_repo ----------------------------------------------------


def test_list_engagements_filters_by_strategist_email():
    captured: list = []

    def fake_fetch_all(token, query, params):
        captured.append((query, params))
        return []

    with patch.object(engagements_repo.dbsql, "fetch_all", side_effect=fake_fetch_all):
        engagements_repo.list_engagements(
            user_token="OBO",
            strategist_email="alice@databricks.com",
        )
    query, params = captured[0]
    assert "v_engagements_unified" in query
    assert "strategist_email = %(strategist_email)s" in query
    assert params["strategist_email"] == "alice@databricks.com"


def test_list_engagements_with_filters():
    captured: list = []
    with patch.object(
        engagements_repo.dbsql,
        "fetch_all",
        side_effect=lambda *a, **k: captured.append(a) or [],
    ):
        engagements_repo.list_engagements(
            user_token="OBO",
            strategist_email="alice@databricks.com",
            filters={
                "fy": "FY26",
                "engagement_type": "Focus",
                "status": "Ongoing",
                "customer": "Acme",
            },
        )
    _, query, params = captured[0]
    assert "fy = %(fy)s" in query
    assert "engagement_type = %(engagement_type)s" in query
    assert "status = %(status)s" in query
    assert "customer ILIKE %(customer)s" in query
    assert params == {
        "strategist_email": "alice@databricks.com",
        "fy": "FY26",
        "engagement_type": "Focus",
        "status": "Ongoing",
        "customer": "%Acme%",
    }


def test_get_engagement_filters_by_email_and_id():
    captured = {}

    def fake_fetch_one(token, query, params):
        captured["q"] = query
        captured["p"] = params
        return None

    with patch.object(engagements_repo.dbsql, "fetch_one", side_effect=fake_fetch_one):
        engagements_repo.get_engagement(
            user_token="OBO", strategist_email="bob@x.com", engagement_id=42
        )
    assert "WHERE strategist_email = %(strategist_email)s AND id = %(id)s" in captured["q"]
    assert captured["p"] == {"strategist_email": "bob@x.com", "id": 42}


def test_create_engagement_stamps_strategist_email():
    """Caller's email must end up in the INSERT — payload cannot override it."""
    insert_calls: list = []
    select_calls: list = []

    def fake_execute(token, query, params):
        insert_calls.append((query, params))
        return 1

    fake_row = {"id": 99, "engagement_type": "Focus"}

    def fake_fetch_one(token, query, params):
        select_calls.append((query, params))
        return fake_row

    with (
        patch.object(engagements_repo.dbsql, "execute", side_effect=fake_execute),
        patch.object(engagements_repo.dbsql, "fetch_one", side_effect=fake_fetch_one),
    ):
        result = engagements_repo.create_engagement(
            user_token="OBO",
            strategist_email="alice@databricks.com",
            payload={
                "engagement_type": "Focus",
                # Attempt to spoof — must be ignored.
                "strategist_email": "evil@elsewhere.com",
            },
        )
    insert_query, insert_params = insert_calls[0]
    assert "INSERT INTO" in insert_query
    assert "engagements_manual" in insert_query
    assert insert_params["strategist_email"] == "alice@databricks.com"
    assert insert_params["created_by_email"] == "alice@databricks.com"
    assert result == fake_row


def test_update_engagement_filters_by_strategist_email():
    select_calls: list = []
    update_calls: list = []

    def fake_execute(token, query, params):
        update_calls.append((query, params))
        return 1

    def fake_fetch_one(token, query, params):
        select_calls.append((query, params))
        return {"id": 1, "status": "Ongoing"}

    with (
        patch.object(engagements_repo.dbsql, "execute", side_effect=fake_execute),
        patch.object(engagements_repo.dbsql, "fetch_one", side_effect=fake_fetch_one),
    ):
        engagements_repo.update_engagement(
            user_token="OBO",
            strategist_email="alice@databricks.com",
            engagement_id=1,
            payload={"status": "Completed"},
        )
    update_query, update_params = update_calls[0]
    assert "engagements_manual" in update_query
    assert "status = %(status)s" in update_query
    assert "WHERE strategist_email = %(strategist_email)s AND id = %(id)s" in update_query
    assert update_params == {
        "strategist_email": "alice@databricks.com",
        "id": 1,
        "status": "Completed",
    }


def test_delete_engagement_filters_by_strategist_email():
    captured = {}

    def fake_execute(token, query, params):
        captured["q"] = query
        captured["p"] = params
        return 1

    with patch.object(engagements_repo.dbsql, "execute", side_effect=fake_execute):
        engagements_repo.delete_engagement(
            user_token="OBO", strategist_email="alice@databricks.com", engagement_id=7
        )
    assert "DELETE FROM" in captured["q"]
    assert "WHERE strategist_email = %(strategist_email)s AND id = %(id)s" in captured["q"]
    assert captured["p"] == {"strategist_email": "alice@databricks.com", "id": 7}


def test_two_strategists_get_disjoint_queries():
    """Same operation from two emails must produce distinct WHERE bindings."""
    bindings: list = []

    def fake_fetch_all(token, query, params):
        bindings.append(params["strategist_email"])
        return []

    with patch.object(engagements_repo.dbsql, "fetch_all", side_effect=fake_fetch_all):
        engagements_repo.list_engagements(
            user_token="OBO-A", strategist_email="alice@x.com"
        )
        engagements_repo.list_engagements(
            user_token="OBO-B", strategist_email="bob@x.com"
        )
    assert bindings == ["alice@x.com", "bob@x.com"]


# --- projects_repo -------------------------------------------------------


def test_list_projects_filters_by_strategist_email():
    captured = {}

    def fake_fetch_all(token, query, params):
        captured["q"] = query
        captured["p"] = params
        return []

    with patch.object(projects_repo.dbsql, "fetch_all", side_effect=fake_fetch_all):
        projects_repo.list_projects(user_token="OBO", strategist_email="alice@x.com")
    assert "FROM main.field_strategist_cockpit.projects" in captured["q"]
    assert "WHERE strategist_email = %(strategist_email)s" in captured["q"]
    assert captured["p"] == {"strategist_email": "alice@x.com"}


def test_create_project_stamps_strategist_email_and_creator():
    insert_calls: list = []
    select_calls: list = []
    fake_row = {"id": 1, "name": "Demo", "url": "https://x"}

    def fake_execute(token, query, params):
        insert_calls.append((query, params))
        return 1

    def fake_fetch_one(token, query, params):
        select_calls.append((query, params))
        return fake_row

    with (
        patch.object(projects_repo.dbsql, "execute", side_effect=fake_execute),
        patch.object(projects_repo.dbsql, "fetch_one", side_effect=fake_fetch_one),
    ):
        projects_repo.create_project(
            user_token="OBO",
            strategist_email="alice@databricks.com",
            payload={"name": "Demo", "url": "https://x", "category": "Application"},
        )
    insert_query, insert_params = insert_calls[0]
    assert "INSERT INTO" in insert_query
    assert insert_params["strategist_email"] == "alice@databricks.com"
    assert insert_params["created_by_email"] == "alice@databricks.com"
    assert insert_params["name"] == "Demo"
    assert insert_params["url"] == "https://x"


def test_delete_project_blocks_non_owner_non_admin(monkeypatch):
    """Non-owner gets the same answer non-existent does (False)."""
    monkeypatch.delenv("ADMIN_EMAILS", raising=False)
    monkeypatch.setenv("ADMIN_EMAILS", "ops@x.com")

    def fake_fetch_one(token, query, params):
        return {"created_by_email": "alice@x.com"}

    execute_calls: list = []

    def fake_execute(token, query, params):
        execute_calls.append((query, params))
        return 1

    with (
        patch.object(projects_repo.dbsql, "fetch_one", side_effect=fake_fetch_one),
        patch.object(projects_repo.dbsql, "execute", side_effect=fake_execute),
    ):
        ok = projects_repo.delete_project(
            user_token="OBO", strategist_email="bob@x.com", project_id=1
        )
    assert ok is False
    assert execute_calls == []  # no DELETE issued


def test_delete_project_allows_creator():
    def fake_fetch_one(token, query, params):
        return {"created_by_email": "alice@x.com"}

    execute_calls: list = []

    def fake_execute(token, query, params):
        execute_calls.append((query, params))
        return 1

    with (
        patch.object(projects_repo.dbsql, "fetch_one", side_effect=fake_fetch_one),
        patch.object(projects_repo.dbsql, "execute", side_effect=fake_execute),
    ):
        ok = projects_repo.delete_project(
            user_token="OBO", strategist_email="alice@x.com", project_id=1
        )
    assert ok is True
    assert len(execute_calls) == 1
    assert "DELETE FROM" in execute_calls[0][0]


def test_delete_project_allows_admin(monkeypatch):
    monkeypatch.setenv("ADMIN_EMAILS", "ops@x.com")

    def fake_fetch_one(token, query, params):
        return {"created_by_email": "alice@x.com"}

    execute_calls: list = []

    def fake_execute(token, query, params):
        execute_calls.append((query, params))
        return 1

    with (
        patch.object(projects_repo.dbsql, "fetch_one", side_effect=fake_fetch_one),
        patch.object(projects_repo.dbsql, "execute", side_effect=fake_execute),
    ):
        ok = projects_repo.delete_project(
            user_token="OBO", strategist_email="ops@x.com", project_id=1
        )
    assert ok is True
    assert len(execute_calls) == 1


# --- HTTP-level dispatch on DATA_BACKEND=dbsql --------------------------


def test_engagements_router_dispatches_to_dbsql_when_flag_set(client, monkeypatch):
    """When data_backend=dbsql the router must call into the repo, not the ORM."""
    from src.backend.config import settings

    monkeypatch.setattr(settings, "data_backend", "dbsql")

    captured: list = []

    def fake_fetch_all(token, query, params):
        captured.append((token, query, params))
        return [
            {
                "id": 1,
                "engagement_type": "Focus",
                "status": "Ongoing",
                "customer": "Acme",
                "engagement_title": "Demo",
                "actionable_outcome": None,
                "ae": None,
                "asq_url": None,
                "asq_id": None,
                "timeframe": None,
                "fy": "FY26",
                "quarter": "FY26Q1",
                "related_documents": None,
                "next_steps": None,
                "uco_ids": None,
            }
        ]

    with patch.object(engagements_repo.dbsql, "fetch_all", side_effect=fake_fetch_all):
        resp = client.get(
            "/api/engagements/",
            headers={
                "X-Forwarded-Email": "alice@databricks.com",
                "X-Forwarded-Access-Token": "OBO-token",
            },
        )
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["customer"] == "Acme"
    # Critical: tenancy filter binding came from the auth dep, not the URL.
    token, query, params = captured[0]
    assert token == "OBO-token"
    assert params["strategist_email"] == "alice@databricks.com"


def test_projects_router_dispatches_to_dbsql_when_flag_set(client, monkeypatch):
    from src.backend.config import settings

    monkeypatch.setattr(settings, "data_backend", "dbsql")

    captured: list = []

    def fake_fetch_all(token, query, params):
        captured.append((token, query, params))
        return [
            {
                "id": 1,
                "strategist_email": "alice@databricks.com",
                "name": "Demo",
                "description": None,
                "url": "https://x",
                "thumbnail_url": None,
                "category": "Application",
                "created_at": None,
                "created_by_email": "alice@databricks.com",
            }
        ]

    with patch.object(projects_repo.dbsql, "fetch_all", side_effect=fake_fetch_all):
        resp = client.get(
            "/api/projects/",
            headers={
                "X-Forwarded-Email": "alice@databricks.com",
                "X-Forwarded-Access-Token": "OBO",
            },
        )
    assert resp.status_code == 200
    assert resp.json()[0]["name"] == "Demo"
    _, query, params = captured[0]
    assert "main.field_strategist_cockpit.projects" in query
    assert params["strategist_email"] == "alice@databricks.com"
