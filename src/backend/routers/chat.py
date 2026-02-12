import os
import logging
from fastapi import APIRouter, HTTPException

from src.backend.schemas import ChatMessage, ChatResponse
from src.backend.config import settings

router = APIRouter(prefix="/api/chat", tags=["chat"])
logger = logging.getLogger(__name__)


def _query_stratego(message: str) -> str:
    """Query the Stratego Knowledge Assistant endpoint."""
    endpoint_name = settings.stratego_endpoint_name
    if not endpoint_name:
        return _fallback_response(message)

    try:
        from databricks.sdk import WorkspaceClient

        w = WorkspaceClient()
        response = w.serving_endpoints.query(
            name=endpoint_name,
            messages=[{"role": "user", "content": message}],
        )
        if response and response.choices:
            return response.choices[0].message.content
        return _fallback_response(message)
    except Exception as e:
        logger.warning(f"Stratego KA query failed: {e}")
        return _fallback_response(message)


def _fallback_response(message: str) -> str:
    """Provide a helpful fallback when KA is not available."""
    msg_lower = message.lower()

    if any(w in msg_lower for w in ["hello", "hi", "hey", "greet", "welcome"]):
        return (
            "Hello! I'm Stratego, your strategic advisory companion. "
            "I can help you navigate your engagements, explore the strategist canvas, "
            "and find reusable assets. What would you like to explore today?"
        )

    if any(w in msg_lower for w in ["focus", "strategic advisor"]):
        return (
            "Focus engagements are multi-quarter strategic advisory relationships, "
            "indicated by the 'Strategic Advisor' flag at the account level in Salesforce. "
            "Current/recent focus accounts include Deutsche Boerse (AI-centered stock exchange), "
            "Deutsche Telekom (landing the platform), and several completed ones like "
            "Continental, E.ON, Viessmann, ZF, and Telefonica. "
            "Check the Impact Dashboard filtered by 'Focus' to see the full picture."
        )

    if any(w in msg_lower for w in ["one-off", "asq", "one off"]):
        return (
            "One-off engagements are typically single-quarter exercises tracked as ASQ "
            "(Approval Requests) in Salesforce. These range from keynotes and vision sessions "
            "to competitive deal support and RFP responses. "
            "The Impact Dashboard shows all one-off engagements with their status and timeline."
        )

    if any(w in msg_lower for w in ["engagement", "account", "customer"]):
        return (
            "Check out the Impact Dashboard for a full view of your engagements across "
            "fiscal years and territories. You can filter by Focus vs One-off engagements "
            "and track progress over time. The portfolio spans major enterprises like "
            "Deutsche Boerse, Deutsche Telekom, Mercedes, E.ON, Continental, and more."
        )

    if any(w in msg_lower for w in ["canvas", "framework", "role", "activity"]):
        return (
            "The Strategist Canvas maps activities across five pillars: "
            "1) Thought Leadership (50% - customer engagements + 10% evangelism), "
            "2) Coaching & Mentoring, 3) Customer Mobilization, "
            "4) Initiatives (20%), and 5) Admin & Research. "
            "Click any box on the Canvas page to see related engagements and materials."
        )

    if any(w in msg_lower for w in ["fy", "fiscal", "quarter", "year"]):
        return (
            "Databricks fiscal year starts in February: "
            "FY25 = Feb 2024 - Jan 2025, FY26 = Feb 2025 - Jan 2026, "
            "FY27 = Feb 2026 - Jan 2027. "
            "Use the FY filter on the Impact Dashboard to view engagements by period."
        )

    if any(w in msg_lower for w in ["dashboard", "impact", "metric"]):
        return (
            "The Impact Dashboard tracks key metrics: total engagements, "
            "focus accounts, unique customers, and engagement distribution by quarter. "
            "It includes filters for FY, engagement type, and status. "
            "Navigate to the Impact page or view the full AI/BI Dashboard in Databricks."
        )

    if any(w in msg_lower for w in ["project", "gallery", "asset", "template"]):
        return (
            "The Projects Gallery contains reusable artefacts like 'Systems of Intelligence' "
            "(a strategic framework presentation) and the 'Innovation Factory' app. "
            "You can add new projects with a name, URL, and description."
        )

    if any(w in msg_lower for w in ["genie", "ask data", "sql", "query"]):
        return (
            "You can use the Genie Space to ask natural language questions about your "
            "engagement data. Try questions like 'Which accounts had focus engagements "
            "in FY26?' or 'What is the total revenue for accounts I engaged with?'"
        )

    return (
        "I'm here to help you navigate the Strategist Cockpit. "
        "Try asking about: your engagements, focus vs one-off, the strategist canvas, "
        "fiscal year details, the impact dashboard, projects gallery, or specific accounts."
    )


@router.post("/", response_model=ChatResponse)
async def chat(message: ChatMessage):
    try:
        response_text = _query_stratego(message.message)
        return ChatResponse(response=response_text, source="stratego")
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail="Failed to process chat message")
