"""Stratego chat router.

Proxies user messages to a Databricks Knowledge Assistant Model Serving endpoint
when STRATEGO_ENDPOINT_NAME is set. When not configured (local dev without
credentials), returns a single short offline message — we intentionally don't
try to be clever offline. The Stratego "knowledge" lives in the KA endpoint's
attached context, not in this file.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from src.backend.config import settings
from src.backend.schemas import ChatMessage, ChatResponse

router = APIRouter(prefix="/api/chat", tags=["chat"])
logger = logging.getLogger(__name__)

OFFLINE_RESPONSE = (
    "Stratego is offline in this environment. Set STRATEGO_ENDPOINT_NAME to the "
    "Databricks Model Serving endpoint for your Knowledge Assistant to enable chat."
)


def _query_stratego(message: str) -> str:
    """Query the Stratego Knowledge Assistant endpoint. Return the offline
    response if the endpoint is not configured or the call fails."""
    endpoint_name = settings.stratego_endpoint_name
    if not endpoint_name:
        return OFFLINE_RESPONSE

    try:
        from databricks.sdk import WorkspaceClient  # imported lazily — dev-only SDK dep

        client = WorkspaceClient()
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
async def chat(message: ChatMessage) -> ChatResponse:
    try:
        text = _query_stratego(message.message)
    except Exception as exc:  # noqa: BLE001 — defence-in-depth; inner handler already catches
        logger.error("Chat error: %s", exc)
        raise HTTPException(
            status_code=500, detail="Failed to process chat message"
        ) from exc
    return ChatResponse(response=text, source="stratego")
