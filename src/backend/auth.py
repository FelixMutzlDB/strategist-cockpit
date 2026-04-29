"""User-identity dependencies for the Databricks Apps OBO model.

Databricks Apps inject ``X-Forwarded-Email`` and ``X-Forwarded-Access-Token``
headers on every request reaching the container. We treat the email header
as the authoritative user identity for audit, ownership, and (eventually)
per-row tenancy filtering.

Local dev does not have the Apps proxy in front, so a fallback email is used
unless ``STRICT_AUTH`` is set. This lets ``npm run dev`` and pytest keep
working without faking headers everywhere. In production (Databricks Apps),
``app.yaml`` should set ``STRICT_AUTH=1`` so a missing header is a hard 401
rather than silently routing to the dev fallback.
"""

from __future__ import annotations

import os

from fastapi import Header, HTTPException


def _strict_auth_enabled() -> bool:
    return os.environ.get("STRICT_AUTH", "").strip().lower() in ("1", "true", "yes")


def _dev_fallback_email() -> str:
    return os.environ.get("DEV_USER_EMAIL", "dev@local").strip().lower()


def _admin_emails() -> set[str]:
    raw = os.environ.get(
        "ADMIN_EMAILS",
        "felix.mutzl@databricks.com,marco.metting@databricks.com",
    )
    return {part.strip().lower() for part in raw.split(",") if part.strip()}


def current_user_email(
    x_forwarded_email: str | None = Header(default=None, alias="X-Forwarded-Email"),
) -> str:
    """FastAPI dependency: return the authenticated user's email (lower-case).

    Production (``STRICT_AUTH=1``): missing header → 401.
    Dev: missing header → ``DEV_USER_EMAIL`` env var or ``dev@local``.
    """
    if x_forwarded_email:
        return x_forwarded_email.strip().lower()
    if _strict_auth_enabled():
        raise HTTPException(status_code=401, detail="Missing X-Forwarded-Email")
    return _dev_fallback_email()


def is_admin(email: str) -> bool:
    """True if ``email`` is in the configured admin list (CAN_MANAGE)."""
    return email.strip().lower() in _admin_emails()
