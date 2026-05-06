"""Stratego chat router.

Proxies user messages to a Databricks Knowledge Assistant Model Serving endpoint
when STRATEGO_ENDPOINT_NAME is set. When not configured (local dev without
credentials), returns a single short offline message — we intentionally don't
try to be clever offline. The Stratego "knowledge" lives in the KA endpoint's
attached context, not in this file.

Auth model (T-205 / F-TM-2): the WorkspaceClient is constructed per-request
with the user's OBO token (``X-Forwarded-Access-Token``), so the KA call is
authorized as the strategist, not the app service principal. ``app.yaml``
must declare the ``serving.serving-endpoints`` user-authorization scope.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from src.backend.audit import record_event
from src.backend.auth import current_user_email, current_user_token_or_empty
from src.backend.config import settings
from src.backend.schemas import ChatMessage, ChatResponse

router = APIRouter(prefix="/api/chat", tags=["chat"])
logger = logging.getLogger(__name__)

OFFLINE_RESPONSE = (
    "Stratego is offline in this environment. Set STRATEGO_ENDPOINT_NAME to the "
    "Databricks Model Serving endpoint for your Knowledge Assistant to enable chat."
)


def _query_stratego(message: str, user_token: str) -> str:
    """Query the Stratego Knowledge Assistant endpoint as the calling user.

    Returns the offline response if the endpoint is not configured or the
    call fails. ``user_token`` is the OBO token from
    ``current_user_token()`` — never the app SP.
    """
    endpoint_name = settings.stratego_endpoint_name
    if not endpoint_name:
        return OFFLINE_RESPONSE

    try:
        from databricks.sdk import WorkspaceClient  # imported lazily — dev-only SDK dep

        client = WorkspaceClient(host=settings.databricks_host or None, token=user_token)
        response = client.serving_endpoints.query(
            name=endpoint_name,
            messages=[{"role": "user", "content": message}],
        )
    except Exception as exc:  # noqa: BLE001 — any SDK/network failure is the same user outcome
        logger.warning("Stratego KA query failed: %s", exc)
        return OFFLINE_RESPONSE

    if response and getattr(response, "choices", None):
        choice = response.choices[0]
        content = getattr(getattr(choice, "message", None), "content", None)
        if content:
            return content
    return OFFLINE_RESPONSE


@router.post("/", response_model=ChatResponse)
async def chat(
    message: ChatMessage,
    user_email: str = Depends(current_user_email),
    user_token: str = Depends(current_user_token_or_empty),
) -> ChatResponse:
    prompt_length = len(message.message)
    try:
        text = _query_stratego(message.message, user_token)
    except Exception as exc:  # noqa: BLE001 — defence-in-depth; inner handler already catches
        logger.error("Chat error: %s", exc)
        record_event(
            user_email=user_email,
            action="chat",
            target_type="stratego_ka",
            result="error",
            extra={
                "prompt_length": prompt_length,
                "error_class": type(exc).__name__,
            },
            user_token=user_token,
        )
        raise HTTPException(
            status_code=500, detail="Failed to process chat message"
        ) from exc
    record_event(
        user_email=user_email,
        action="chat",
        target_type="stratego_ka",
        extra={"prompt_length": prompt_length},
        user_token=user_token,
    )
    return ChatResponse(response=text, source="stratego")
