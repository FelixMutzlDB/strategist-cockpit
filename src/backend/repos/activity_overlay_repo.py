"""T-212 activity overlay repository.

One unified Delta overlay (``main.field_strategist_cockpit.activity_app_data``)
that stores qualitative impact tags + free-text notes for any activity in
any of the five engagement categories — customer / evangelism / initiative
/ planning / exec_meeting. Keyed by ``(category, activity_key, strategist_email)``.

Tenancy contract (mirrors T-206 ``customer_engagements_repo`` exactly):

- ``strategist_email`` is **always** the caller's email (passed in by the
  router from ``current_user_email()``). NEVER read from a request payload.
- Every SELECT filters by ``strategist_email`` so Alice's tags can never
  surface in Bob's response.
- ``set_tags()`` runs a Delta ``MERGE INTO`` so callers can upsert without
  pre-checking existence.

The dev/test path goes through ``data_backend=sqlite`` and a parallel
``ActivityOverlay`` ORM model — same shape, JSON-encoded ``impact_tags``.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from src.backend import dbsql
from src.backend.config import settings


def _qual(table: str) -> str:
    return f"{settings.uc_catalog}.{settings.uc_schema}.{table}"


# --- DBSQL backend -------------------------------------------------------


def get_tags(
    *,
    user_token: str,
    category: str,
    activity_key: str,
    strategist_email: str,
) -> dict | None:
    """Return ``{"impact_tags": [...], "impact_notes": str|None}`` or None.

    A missing overlay row is not an error — callers default to empty list.
    """
    query = (
        f"SELECT impact_tags, impact_notes "
        f"FROM {_qual('activity_app_data')} "
        f"WHERE category = %(category)s "
        f"AND activity_key = %(activity_key)s "
        f"AND strategist_email = %(strategist_email)s"
    )
    row = dbsql.fetch_one(
        user_token,
        query,
        {
            "category": category,
            "activity_key": activity_key,
            "strategist_email": strategist_email,
        },
    )
    if row is None:
        return None
    # ``databricks-sql-connector`` returns ARRAY<STRING> as a list; normalise
    # in case it comes back as a tuple or None.
    tags = row.get("impact_tags") or []
    return {
        "impact_tags": list(tags),
        "impact_notes": row.get("impact_notes"),
    }


def set_tags(
    *,
    user_token: str,
    category: str,
    activity_key: str,
    strategist_email: str,
    tags: list[str],
    notes: str | None,
) -> None:
    """Upsert the overlay row for ``(category, activity_key, caller)``.

    Uses Delta ``MERGE INTO`` so this is the only repo call needed on the
    write path — no SELECT-then-INSERT-or-UPDATE.
    """
    merge_sql = (
        f"MERGE INTO {_qual('activity_app_data')} t "
        f"USING (SELECT "
        f"  %(category)s AS category, "
        f"  %(activity_key)s AS activity_key, "
        f"  %(strategist_email)s AS strategist_email, "
        f"  %(impact_tags)s AS impact_tags, "
        f"  %(impact_notes)s AS impact_notes, "
        f"  %(updated_at)s AS updated_at "
        f") s "
        f"ON t.category = s.category "
        f"AND t.activity_key = s.activity_key "
        f"AND t.strategist_email = s.strategist_email "
        f"WHEN MATCHED THEN UPDATE SET "
        f"  impact_tags = s.impact_tags, "
        f"  impact_notes = s.impact_notes, "
        f"  updated_at = s.updated_at "
        f"WHEN NOT MATCHED THEN INSERT "
        f"  (category, activity_key, strategist_email, impact_tags, impact_notes, updated_at) "
        f"VALUES "
        f"  (s.category, s.activity_key, s.strategist_email, s.impact_tags, s.impact_notes, s.updated_at)"
    )
    params: dict[str, Any] = {
        "category": category,
        "activity_key": activity_key,
        # Tenant key always stamped from caller — never from a payload.
        "strategist_email": strategist_email,
        "impact_tags": list(tags),
        "impact_notes": notes,
        "updated_at": datetime.now(timezone.utc),
    }
    dbsql.execute(user_token, merge_sql, params)


# --- SQLite dev mirror ---------------------------------------------------


def get_tags_sqlite(
    db,
    *,
    category: str,
    activity_key: str,
    strategist_email: str,
) -> dict | None:
    """SQLite parity helper. ``db`` is a SQLAlchemy ``Session``."""
    from src.backend.models import ActivityOverlay

    row = (
        db.query(ActivityOverlay)
        .filter(
            ActivityOverlay.category == category,
            ActivityOverlay.activity_key == activity_key,
            ActivityOverlay.strategist_email == strategist_email,
        )
        .first()
    )
    if row is None:
        return None
    tags = json.loads(row.impact_tags) if row.impact_tags else []
    return {"impact_tags": tags, "impact_notes": row.impact_notes}


def set_tags_sqlite(
    db,
    *,
    category: str,
    activity_key: str,
    strategist_email: str,
    tags: list[str],
    notes: str | None,
) -> None:
    from src.backend.models import ActivityOverlay

    encoded = json.dumps(list(tags))
    now = datetime.now(timezone.utc)
    row = (
        db.query(ActivityOverlay)
        .filter(
            ActivityOverlay.category == category,
            ActivityOverlay.activity_key == activity_key,
            ActivityOverlay.strategist_email == strategist_email,
        )
        .first()
    )
    if row is None:
        db.add(
            ActivityOverlay(
                category=category,
                activity_key=activity_key,
                strategist_email=strategist_email,
                impact_tags=encoded,
                impact_notes=notes,
                updated_at=now,
            )
        )
    else:
        row.impact_tags = encoded
        row.impact_notes = notes
        row.updated_at = now
    db.commit()


# --- Helpers -------------------------------------------------------------


def customer_engagement_key(engagement_row: dict) -> str:
    """Build a stable ``activity_key`` for a customer engagement row.

    ``asq:<id>`` for SFDC-backed rows; ``manual:<id>`` for orphan rows in
    ``customer_engagements_manual``. The unified view stores SFDC rows
    with ``asq_id`` populated and ``id`` as the SFDC id; orphan rows have
    a BIGINT IDENTITY ``id`` and no ``asq_id``.
    """
    asq_id = engagement_row.get("asq_id")
    if asq_id:
        return f"asq:{asq_id}"
    return f"manual:{engagement_row.get('id')}"
