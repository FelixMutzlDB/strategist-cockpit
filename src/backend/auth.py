"""User-identity dependencies for the Databricks Apps OBO model.

Databricks Apps inject ``X-Forwarded-Email`` and ``X-Forwarded-Access-Token``
headers on every request reaching the container. We treat the email header
as the authoritative user identity for audit, ownership, and (eventually)
per-row tenancy filtering. The access-token header is the user's OBO token
that downstream Databricks calls (SQL warehouse, serving endpoints, Genie)
must use so authorization is evaluated against the user, not the app SP.

Local dev does not have the Apps proxy in front, so fallbacks kick in:
- Missing email header → ``DEV_USER_EMAIL`` (or ``dev@local``).
- Missing token header → ``DATABRICKS_TOKEN`` env var, with a one-shot
  warning so it's never silently confused with prod.

In production (Databricks Apps), ``app.yaml`` should set ``STRICT_AUTH=1``
so a missing header is a hard 401 rather than routing to the dev fallback.
"""

from __future__ import annotations

import logging
import os

from fastapi import Header, HTTPException

logger = logging.getLogger(__name__)

_DEV_TOKEN_FALLBACK_LOGGED = False


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


def current_user_token(
    x_forwarded_access_token: str | None = Header(
        default=None, alias="X-Forwarded-Access-Token"
    ),
) -> str:
    """FastAPI dependency: return the user's OBO access token.

    Production (``STRICT_AUTH=1``): missing header → 401.
    Dev: missing header → ``DATABRICKS_TOKEN`` env var (with a one-shot
    warning so prod misconfigurations don't silently degrade). If neither
    is available raises 401 — there's no point returning an empty token to
    a downstream Databricks call.
    """
    global _DEV_TOKEN_FALLBACK_LOGGED
    if x_forwarded_access_token:
        return x_forwarded_access_token
    if _strict_auth_enabled():
        raise HTTPException(
            status_code=401, detail="Missing X-Forwarded-Access-Token"
        )
    fallback = os.environ.get("DATABRICKS_TOKEN", "").strip()
    if fallback:
        if not _DEV_TOKEN_FALLBACK_LOGGED:
            logger.warning(
                "OBO header missing — falling back to DATABRICKS_TOKEN. "
                "This is dev-mode only; prod must set STRICT_AUTH=1."
            )
            _DEV_TOKEN_FALLBACK_LOGGED = True
        return fallback
    raise HTTPException(
        status_code=401,
        detail="No user token available (set DATABRICKS_TOKEN for dev or "
        "deploy under Databricks Apps for OBO).",
    )


def is_admin(email: str) -> bool:
    """True if ``email`` is in the configured admin list (CAN_MANAGE)."""
    return email.strip().lower() in _admin_emails()
