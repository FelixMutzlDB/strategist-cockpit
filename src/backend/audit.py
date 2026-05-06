"""Per-user structured audit logging for state-changing operations.

Every state-changing route (engagement/project create/update/delete, chat
proxy) calls :func:`record_event` so we have a forensic trail attributable to
the logged-in user.

Events are always emitted as structured JSON to stdout under the
``strategist_cockpit.audit`` logger so a stdout-tailing log pipeline still
captures them. When ``DATA_BACKEND=dbsql`` and the caller passes their OBO
token, events are *additionally* persisted to
``main.field_strategist_cockpit.app_audit_log`` (T-206 / F-TM-4 closure).
The Delta write is best-effort: a warehouse hiccup logs a warning but does
not fail the user's request — the stdout sink is the durable fallback for
forensics, the Delta sink is for queryability.

Never log the **content** of an action — only metadata. For chat we record
``prompt_length`` (a non-sensitive byte count), never the prompt text.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from typing import Any

from src.backend.config import settings

logger = logging.getLogger("strategist_cockpit.audit")

_CANONICAL_FIELDS = ("ts", "user_email", "action", "target_type", "target_id", "result")


def _emit_to_delta(event: dict[str, Any], user_token: str | None) -> None:
    """Best-effort write of one audit event to ``app_audit_log``.

    Silent no-op when the data backend isn't ``dbsql`` or no user token is
    available (dev mode). Warehouse / connector failures are logged at
    WARNING level so they're visible without taking down the user request —
    audit is observability, not transactional state.
    """
    if settings.data_backend != "dbsql" or not user_token:
        return

    # Lazy import — avoids pulling the connector during pytest collection
    # for tests that mock dbsql at the call site.
    from src.backend import dbsql

    try:
        ts_dt = datetime.fromtimestamp(event["ts"] / 1000, tz=timezone.utc)
        target_id_value = event.get("target_id")
        target_id_str = (
            str(target_id_value) if target_id_value is not None else None
        )
        # Anything not in the canonical schema goes into the JSON `extra`.
        extra_dict = {k: v for k, v in event.items() if k not in _CANONICAL_FIELDS}
        extra_json = json.dumps(extra_dict, default=str) if extra_dict else None

        table = f"{settings.uc_catalog}.{settings.uc_schema}.app_audit_log"
        dbsql.execute(
            user_token,
            f"INSERT INTO {table} "
            "(ts, user_email, action, target_type, target_id, result, extra) "
            "VALUES (%(ts)s, %(user_email)s, %(action)s, %(target_type)s, "
            "%(target_id)s, %(result)s, %(extra)s)",
            {
                "ts": ts_dt,
                "user_email": event["user_email"],
                "action": event["action"],
                "target_type": event["target_type"],
                "target_id": target_id_str,
                "result": event["result"],
                "extra": extra_json,
            },
        )
    except Exception as exc:  # noqa: BLE001 — audit failures must never propagate
        logger.warning("Audit Delta sink failed: %s", exc)


def record_event(
    *,
    user_email: str,
    action: str,
    target_type: str,
    target_id: str | int | None = None,
    result: str = "success",
    extra: dict[str, Any] | None = None,
    user_token: str | None = None,
) -> None:
    """Emit one structured audit event.

    Always called with kwargs so call sites stay readable and forward-compatible
    if we add fields later. ``extra`` is for non-PII supplemental data
    (e.g. ``{"prompt_length": 42}`` for chat). Caller is responsible for
    keeping ``extra`` content-free.

    ``user_token`` is the strategist's OBO token from
    ``current_user_token_or_empty()``. When provided AND
    ``DATA_BACKEND=dbsql``, the event is mirrored to the
    ``app_audit_log`` Delta table for queryability.
    """
    event: dict[str, Any] = {
        "ts": int(time.time() * 1000),
        "user_email": user_email,
        "action": action,
        "target_type": target_type,
        "target_id": target_id,
        "result": result,
    }
    if extra:
        # Disallow accidentally overwriting the canonical fields above.
        for reserved in _CANONICAL_FIELDS:
            extra.pop(reserved, None)
        event.update(extra)
    logger.info("audit %s", json.dumps(event, default=str))
    _emit_to_delta(event, user_token)
