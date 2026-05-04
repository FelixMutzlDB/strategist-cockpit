"""DBSQL-backed projects repository (T-206 + F-TM-1).

Single Delta table at ``main.field_strategist_cockpit.projects``. Every row
carries ``strategist_email`` (tenant) and ``created_by_email`` (creator);
DELETE is gated to creator-or-admin per F-TM-5 (mirrors SQLite behaviour).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from src.backend import dbsql
from src.backend.auth import is_admin
from src.backend.config import settings


def _qual(table: str) -> str:
    return f"{settings.uc_catalog}.{settings.uc_schema}.{table}"


_PROJECT_COLUMNS = (
    "id, strategist_email, name, description, url, thumbnail_url, "
    "category, created_at, created_by_email"
)


def list_projects(*, user_token: str, strategist_email: str) -> list[dict]:
    query = (
        f"SELECT {_PROJECT_COLUMNS} "
        f"FROM {_qual('projects')} "
        f"WHERE strategist_email = %(strategist_email)s "
        f"ORDER BY created_at DESC"
    )
    return dbsql.fetch_all(
        user_token, query, {"strategist_email": strategist_email}
    )


def create_project(
    *,
    user_token: str,
    strategist_email: str,
    payload: dict[str, Any],
) -> dict:
    now = datetime.now(timezone.utc)
    insert_sql = (
        f"INSERT INTO {_qual('projects')} "
        "(strategist_email, name, description, url, thumbnail_url, category, "
        "created_at, created_by_email) "
        "VALUES (%(strategist_email)s, %(name)s, %(description)s, %(url)s, "
        "%(thumbnail_url)s, %(category)s, %(created_at)s, %(created_by_email)s)"
    )
    params = {
        "strategist_email": strategist_email,
        "name": payload["name"],
        "description": payload.get("description"),
        "url": payload["url"],
        "thumbnail_url": payload.get("thumbnail_url"),
        "category": payload.get("category"),
        "created_at": now,
        "created_by_email": strategist_email,
    }
    dbsql.execute(user_token, insert_sql, params)

    select_sql = (
        f"SELECT {_PROJECT_COLUMNS} "
        f"FROM {_qual('projects')} "
        f"WHERE strategist_email = %(strategist_email)s "
        f"AND created_at = %(created_at)s "
        f"ORDER BY id DESC LIMIT 1"
    )
    row = dbsql.fetch_one(
        user_token,
        select_sql,
        {"strategist_email": strategist_email, "created_at": now},
    )
    if row is None:
        raise RuntimeError("Insert succeeded but follow-up SELECT returned no row.")
    return row


def delete_project(
    *,
    user_token: str,
    strategist_email: str,
    project_id: int,
) -> bool:
    """Delete a project. Returns True on success, False on not-found / not-yours.

    Behaviour mirrors the SQLite path: callers that aren't creator-or-admin
    get the same 'not found' answer non-owners do, so existence isn't leaked.
    """
    select_sql = (
        f"SELECT created_by_email FROM {_qual('projects')} "
        f"WHERE strategist_email = %(strategist_email)s AND id = %(id)s"
    )
    row = dbsql.fetch_one(
        user_token,
        select_sql,
        {"strategist_email": strategist_email, "id": project_id},
    )
    if row is None:
        return False
    creator = (row.get("created_by_email") or "").lower()
    if creator != strategist_email.lower() and not is_admin(strategist_email):
        return False

    delete_sql = (
        f"DELETE FROM {_qual('projects')} "
        f"WHERE strategist_email = %(strategist_email)s AND id = %(id)s"
    )
    dbsql.execute(
        user_token,
        delete_sql,
        {"strategist_email": strategist_email, "id": project_id},
    )
    return True
