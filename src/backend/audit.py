"""Per-user structured audit logging for state-changing operations.

Every state-changing route (engagement/project create/update/delete, chat
proxy) calls :func:`record_event` so we have a forensic trail attributable to
the logged-in user.

For now events are emitted as structured JSON to stdout under the
``strategist_cockpit.audit`` logger. T-206 will plumb these into a Delta
table at ``main.field_strategist_cockpit.app_audit_log`` so they're queryable.

Never log the **content** of an action — only metadata. For chat we record
``prompt_length`` (a non-sensitive byte count), never the prompt text.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

logger = logging.getLogger("strategist_cockpit.audit")


def record_event(
    *,
    user_email: str,
    action: str,
    target_type: str,
    target_id: str | int | None = None,
    result: str = "success",
    extra: dict[str, Any] | None = None,
) -> None:
    """Emit one structured audit event.

    Always called with kwargs so call sites stay readable and forward-compatible
    if we add fields later. ``extra`` is for non-PII supplemental data
    (e.g. ``{"prompt_length": 42}`` for chat). Caller is responsible for
    keeping ``extra`` content-free.
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
        for reserved in ("ts", "user_email", "action", "target_type", "target_id", "result"):
            extra.pop(reserved, None)
        event.update(extra)
    logger.info("audit %s", json.dumps(event, default=str))
