"""DBSQL-backed customer engagements repository (T-206 + F-TM-1).

Read source: ``main.field_strategist_cockpit.v_customer_engagements_unified``
— the joined view of SFDC ASQs (`asq_uco`) UNIONed with manual orphans
(`customer_engagements_manual`) and LEFT-joined to revenue + app overlay.

Write targets:
- ``customer_engagements_manual`` for new orphan customer engagements.
- ``customer_engagement_app_data`` for per-engagement overlay (next_steps,
  related_documents). Today these fields are stored on
  ``customer_engagements_manual`` for orphans; the overlay table is
  reserved for SFDC ASQs that the strategist wants to annotate but cannot
  edit at source.

Tenancy: every SELECT filters by ``strategist_email``; every INSERT stamps it.
Updates and deletes against the unified view are scoped to *manual* rows —
SFDC ASQs are read-only from the cockpit (their truth lives in Salesforce).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from src.backend import dbsql
from src.backend.config import settings
from src.backend.repos import activity_overlay_repo


def _qual(table: str) -> str:
    """Fully-qualify a table or view name with the configured UC namespace."""
    return f"{settings.uc_catalog}.{settings.uc_schema}.{table}"


# T-212: fields handled by the overlay repo, not the manual table.
_OVERLAY_FIELDS = ("impact_tags", "impact_notes")


def _attach_overlay(
    row: dict | None,
    *,
    user_token: str,
    strategist_email: str,
) -> dict | None:
    """Mutate ``row`` to include ``impact_tags`` / ``impact_notes`` from the overlay."""
    if row is None:
        return None
    key = activity_overlay_repo.customer_engagement_key(row)
    overlay = activity_overlay_repo.get_tags(
        user_token=user_token,
        category="customer",
        activity_key=key,
        strategist_email=strategist_email,
    )
    if overlay:
        row["impact_tags"] = overlay["impact_tags"]
        row["impact_notes"] = overlay["impact_notes"]
    else:
        row["impact_tags"] = []
        row["impact_notes"] = None
    return row


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
        f"FROM {_qual('v_customer_engagements_unified')} "
        f"WHERE {' AND '.join(where)} "
        f"ORDER BY id DESC"
    )
    rows = dbsql.fetch_all(user_token, query, params)
    for row in rows:
        _attach_overlay(row, user_token=user_token, strategist_email=strategist_email)
    return rows


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
        f"FROM {_qual('v_customer_engagements_unified')} "
        f"WHERE strategist_email = %(strategist_email)s AND id = %(id)s"
    )
    row = dbsql.fetch_one(
        user_token,
        query,
        {"strategist_email": strategist_email, "id": engagement_id},
    )
    return _attach_overlay(row, user_token=user_token, strategist_email=strategist_email)


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
        f"INSERT INTO {_qual('customer_engagements_manual')} ({', '.join(cols)}) "
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
        f"FROM {_qual('customer_engagements_manual')} "
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

    # T-212: if the caller supplied impact tags/notes on create, persist
    # them via the overlay against the freshly-minted manual key.
    overlay_tags = payload.get("impact_tags") or []
    overlay_notes = payload.get("impact_notes")
    if overlay_tags or overlay_notes:
        activity_overlay_repo.set_tags(
            user_token=user_token,
            category="customer",
            activity_key=activity_overlay_repo.customer_engagement_key(row),
            strategist_email=strategist_email,
            tags=list(overlay_tags),
            notes=overlay_notes,
        )
    return _attach_overlay(row, user_token=user_token, strategist_email=strategist_email)


def update_engagement(
    *,
    user_token: str,
    strategist_email: str,
    engagement_id: int,
    payload: dict[str, Any],
) -> dict | None:
    """Update an *orphan* engagement. SFDC ASQs are not updatable here —
    the router pre-checks existence in ``v_customer_engagements_unified``
    first.

    T-212: ``impact_tags`` / ``impact_notes`` are split out of the payload
    and routed to ``activity_app_data`` via ``activity_overlay_repo`` —
    those columns don't live on ``customer_engagements_manual``.
    """
    # Split overlay-bound fields out of the core table payload.
    overlay_payload = {k: payload.pop(k) for k in list(_OVERLAY_FIELDS) if k in payload}

    if payload:
        set_clauses = [f"{k} = %({k})s" for k in payload]
        update_sql = (
            f"UPDATE {_qual('customer_engagements_manual')} "
            f"SET {', '.join(set_clauses)} "
            f"WHERE strategist_email = %(strategist_email)s AND id = %(id)s"
        )
        params = {**payload, "strategist_email": strategist_email, "id": engagement_id}
        dbsql.execute(user_token, update_sql, params)

    # Fetch current state (with overlay) before deciding whether to upsert.
    existing = get_engagement(
        user_token=user_token,
        strategist_email=strategist_email,
        engagement_id=engagement_id,
    )
    if existing is None:
        return None

    if overlay_payload:
        # PATCH semantics: only fields present in the overlay payload change.
        new_tags = overlay_payload.get("impact_tags", existing.get("impact_tags") or [])
        new_notes = overlay_payload.get("impact_notes", existing.get("impact_notes"))
        activity_overlay_repo.set_tags(
            user_token=user_token,
            category="customer",
            activity_key=activity_overlay_repo.customer_engagement_key(existing),
            strategist_email=strategist_email,
            tags=list(new_tags),
            notes=new_notes,
        )
        existing["impact_tags"] = list(new_tags)
        existing["impact_notes"] = new_notes
    return existing


def delete_engagement(
    *,
    user_token: str,
    strategist_email: str,
    engagement_id: int,
) -> None:
    """Delete an orphan engagement. No-op for SFDC ASQs (filter doesn't match)."""
    delete_sql = (
        f"DELETE FROM {_qual('customer_engagements_manual')} "
        f"WHERE strategist_email = %(strategist_email)s AND id = %(id)s"
    )
    dbsql.execute(
        user_token,
        delete_sql,
        {"strategist_email": strategist_email, "id": engagement_id},
    )
