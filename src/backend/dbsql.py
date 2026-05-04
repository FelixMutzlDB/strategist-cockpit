"""Databricks SQL warehouse connection wrapper (T-206).

Goal: open a short-lived connection to the configured warehouse using the
*caller's* OBO token, run one or more statements, return rows as plain dicts.

The wrapper is intentionally thin — no ORM, no schema validation. Each
caller (see ``src/backend/repos/``) is responsible for the SQL it sends and
for shaping rows into pydantic responses.

Tenancy is enforced at the call site: every ``WHERE`` clause filtering
engagements/projects by ``strategist_email`` lives in the repo functions,
not here. This keeps the wrapper unaware of business rules and makes the
filter trivially auditable.

Local dev: when ``DATA_BACKEND=sqlite`` the routers don't call this module
at all. When ``DATA_BACKEND=dbsql`` and the developer is running locally,
``current_user_token()`` falls back to ``DATABRICKS_TOKEN`` so the same
code path works against a personal warehouse.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from src.backend.config import settings

logger = logging.getLogger(__name__)


def _http_path() -> str:
    return f"/sql/1.0/warehouses/{settings.databricks_warehouse_id}"


@contextmanager
def cursor(user_token: str) -> Iterator[Any]:
    """Yield a databricks-sql cursor authorized as the user.

    ``user_token`` must come from ``current_user_token()``. We construct a
    fresh connection per request rather than pooling — the cookbook pattern
    documented at https://apps-cookbook.dev pools per-user, which adds
    complexity for marginal latency wins on a low-RPS internal app.
    """
    if not settings.databricks_host:
        raise RuntimeError(
            "DATABRICKS_HOST is not configured — cannot open SQL warehouse "
            "connection. Set it in app.yaml (prod) or .env (dev)."
        )
    # Lazy import: keeps the connector optional at test-collection time and
    # mirrors how chat.py imports the SDK.
    from databricks import sql

    with sql.connect(
        server_hostname=settings.databricks_host,
        http_path=_http_path(),
        access_token=user_token,
    ) as connection:
        with connection.cursor() as cur:
            yield cur


def fetch_all(user_token: str, query: str, params: dict | None = None) -> list[dict]:
    """Run a SELECT and return rows as a list of dicts.

    ``params`` is a mapping of named-parameter values; the connector binds
    them as ``%(name)s`` in the query (PEP 249 ``paramstyle="pyformat"``).
    Always pass user input via ``params``, never via f-string concatenation.
    """
    with cursor(user_token) as cur:
        cur.execute(query, params or {})
        cols = [d[0] for d in cur.description] if cur.description else []
        rows = cur.fetchall()
        return [dict(zip(cols, row, strict=False)) for row in rows]


def fetch_one(user_token: str, query: str, params: dict | None = None) -> dict | None:
    rows = fetch_all(user_token, query, params)
    return rows[0] if rows else None


def execute(user_token: str, query: str, params: dict | None = None) -> int:
    """Run an INSERT/UPDATE/DELETE and return the affected-row count.

    Note: Databricks SQL Delta tables don't expose a reliable ``rowcount``
    for INSERTs (the connector returns ``-1``). Callers that need post-write
    state should issue a follow-up SELECT rather than trust this number.
    """
    with cursor(user_token) as cur:
        cur.execute(query, params or {})
        return getattr(cur, "rowcount", -1)
