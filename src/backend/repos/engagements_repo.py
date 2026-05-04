"""DBSQL-backed engagements repository (T-206 + F-TM-1).

Read source: ``main.field_strategist_cockpit.v_engagements_unified`` — the
joined view of SFDC ASQs (`asq_uco`) UNIONed with manual orphans
(`engagements_manual`) and LEFT-joined to revenue + app overlay.

Write targets:
- ``engagements_manual`` for new orphan engagements.
- ``engagement_app_data`` for per-engagement overlay (next_steps,
  related_documents). Today these fields are stored on `engagements_manual`
  for orphans; the overlay table is reserved for SFDC ASQs that the
  strategist wants to annotate but cannot edit at source.

Tenancy: every SELECT filters by ``strategist_email``; every INSERT stamps it.
Updates and deletes against the unified view are scoped to *manual* rows —
SFDC ASQs are read-only from the cockpit (their truth lives in Salesforce).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from src.backend import dbsql
from src.backend.config import settings


def _qual(table: str) -> str:
    """Fully-qualify a table or view name with the configured UC namespace."""
    return f"{settings.uc_catalog}.{settings.uc_schema}.{table}"


# --- READS ---------------------------------------------------------------


def list_engagements(
    *,
    user_token: str,
    strategist_email: str,
    filters: dict[str, Any] | None = None,
) -> list[dict]:
    """List engagements for one strategist, optionally filtered.

    Returns a list of dicts shaped like the ``Engagement`` SQLAlchemy model
    so the router can pass them straight into ``EngagementOut.model_validate``.
    """
    where = ["strategist_email = %(strategist_email)s"]
    params: dict[str, Any] = {"strategist_email": strategist_email}
    if filters:
        if filters.get("fy"):
            where.append("fy = %(fy)s")
            params["fy"] = filters["fy"]
        if filters.get("engagement_type"):
            where.append("engagement_type = %(engagement_type)s")
            params["engagement_type"] = filters["engagement_type"]
        if filters.get("status"):
            where.append("status = %(status)s")
            params["status"] = filters["status"]
        if filters.get("customer"):
            where.append("customer ILIKE %(customer)s")
            params["customer"] = f"%{filters['customer']}%"

    query = (
        f"SELECT id, engagement_type, status, customer, engagement_title, "
        f"actionable_outcome, ae, asq_url, asq_id, timeframe, fy, quarter, "
        f"related_documents, next_steps, uco_ids "
        f"FROM {_qual('v_engagements_unified')} "
        f"WHERE {' AND '.join(where)} "
        f"ORDER BY id DESC"
    )
    return dbsql.fetch_all(user_token, query, params)


def get_engagement(
    *,
    user_token: str,
    strategist_email: str,
    engagement_id: int,
) -> dict | None:
    query = (
        f"SELECT id, engagement_type, status, customer, engagement_title, "
        f"actionable_outcome, ae, asq_url, asq_id, timeframe, fy, quarter, "
        f"related_documents, next_steps, uco_ids "
        f"FROM {_qual('v_engagements_unified')} "
        f"WHERE strategist_email = %(strategist_email)s AND id = %(id)s"
    )
    return dbsql.fetch_one(
        user_token,
        query,
        {"strategist_email": strategist_email, "id": engagement_id},
    )


# --- WRITES (manual orphans) ---------------------------------------------


_ORPHAN_FIELDS = (
    "engagement_type",
    "status",
    "customer",
    "engagement_title",
    "actionable_outcome",
    "ae",
    "asq_url",
    "asq_id",
    "timeframe",
    "fy",
    "quarter",
    "uco_ids",
    "related_documents",
    "next_steps",
)


def create_engagement(
    *,
    user_token: str,
    strategist_email: str,
    payload: dict[str, Any],
) -> dict:
    """Insert a new orphan engagement and return it.

    Two round-trips: INSERT ... then SELECT MAX(id) WHERE the create_at we
    just stamped. Delta INSERTs don't return the generated identity, so we
    pin the row by (strategist_email, created_at) — created_at is set
    server-side here for that reason.
    """
    now = datetime.now(timezone.utc)
    cols = list(_ORPHAN_FIELDS) + [
        "strategist_email",
        "created_at",
        "created_by_email",
    ]
    values = ", ".join(f"%({c})s" for c in cols)
    insert_sql = (
        f"INSERT INTO {_qual('engagements_manual')} ({', '.join(cols)}) "
        f"VALUES ({values})"
    )
    params: dict[str, Any] = {c: payload.get(c) for c in _ORPHAN_FIELDS}
    params["strategist_email"] = strategist_email
    params["created_at"] = now
    params["created_by_email"] = strategist_email
    dbsql.execute(user_token, insert_sql, params)

    select_sql = (
        f"SELECT id, engagement_type, status, customer, engagement_title, "
        f"actionable_outcome, ae, asq_url, asq_id, timeframe, fy, quarter, "
        f"related_documents, next_steps, uco_ids "
        f"FROM {_qual('engagements_manual')} "
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


def update_engagement(
    *,
    user_token: str,
    strategist_email: str,
    engagement_id: int,
    payload: dict[str, Any],
) -> dict | None:
    """Update an *orphan* engagement. SFDC ASQs are not updatable here —
    the router pre-checks existence in ``v_engagements_unified`` first."""
    if not payload:
        return get_engagement(
            user_token=user_token,
            strategist_email=strategist_email,
            engagement_id=engagement_id,
        )
    set_clauses = [f"{k} = %({k})s" for k in payload]
    update_sql = (
        f"UPDATE {_qual('engagements_manual')} "
        f"SET {', '.join(set_clauses)} "
        f"WHERE strategist_email = %(strategist_email)s AND id = %(id)s"
    )
    params = {**payload, "strategist_email": strategist_email, "id": engagement_id}
    dbsql.execute(user_token, update_sql, params)
    return get_engagement(
        user_token=user_token,
        strategist_email=strategist_email,
        engagement_id=engagement_id,
    )


def delete_engagement(
    *,
    user_token: str,
    strategist_email: str,
    engagement_id: int,
) -> None:
    """Delete an orphan engagement. No-op for SFDC ASQs (filter doesn't match)."""
    delete_sql = (
        f"DELETE FROM {_qual('engagements_manual')} "
        f"WHERE strategist_email = %(strategist_email)s AND id = %(id)s"
    )
    dbsql.execute(
        user_token,
        delete_sql,
        {"strategist_email": strategist_email, "id": engagement_id},
    )
