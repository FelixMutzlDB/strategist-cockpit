from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.backend.database import get_db
from src.backend.models import Engagement
from src.backend.schemas import CanvasSummary, EngagementOut

router = APIRouter(prefix="/api/canvas", tags=["canvas"])

# Mapping of canvas activity labels to engagement keywords for filtering
CANVAS_ACTIVITY_KEYWORDS: dict[str, list[str]] = {
    "c-level-vision-setting": ["vision", "CIO", "CFO", "CTO", "CDTO", "exec", "board", "leadership"],
    "data-ai-strategy": ["strategy", "data & ai", "data platform", "roadmap", "program"],
    "strategic-hunting": ["hunting", "land", "bid", "RFP", "RFI", "pipeline", "deal"],
    "elevate-the-pitch": ["keynote", "pitch", "presentation", "speak", "talk", "panel"],
    "targeted-customer-engagements": ["workshop", "on-site", "meeting", "discovery", "session"],
    "measuring-success": ["KPI", "impact", "measure", "metric", "tracking", "value"],
    "champion-building": ["champion", "cadence", "relationship", "stakeholder", "engage"],
    "focused-account-planning": ["account planning", "focused account", "territory"],
    "customer-mobilization": ["mobilization", "adoption", "enablement", "fast track", "MVP"],
    "adoption-frameworks": ["adoption", "framework", "self-service", "delivery model"],
    "community-seeding": ["community", "meetup", "event", "conference", "DAIS", "DAIWT"],
    "individual-coaching": ["coaching", "mentoring", "advising"],
    "events": ["event", "keynote", "panel", "conference", "community day", "learning day"],
    "market-scouting": ["scouting", "research", "trends", "innovation"],
    "strategist-role": ["role", "metrics", "organization"],
    "strategy-cop": ["CoP", "community of practice", "strategy community"],
    "reusable-strategy-assets": ["reusable", "asset", "template", "playbook", "framework"],
    "strategy-research": ["research", "PoV", "point of view", "whitepaper"],
}


def _match_engagement(engagement: Engagement, keywords: list[str]) -> bool:
    """Check if engagement text matches any keyword."""
    searchable = " ".join(
        filter(
            None,
            [
                engagement.engagement_title or "",
                engagement.actionable_outcome or "",
                engagement.next_steps or "",
                engagement.engagement_type or "",
            ],
        )
    ).lower()
    return any(kw.lower() in searchable for kw in keywords)


@router.get("/summary/{activity}", response_model=CanvasSummary)
def get_canvas_summary(activity: str, db: Session = Depends(get_db)):
    keywords = CANVAS_ACTIVITY_KEYWORDS.get(activity, [])
    all_engagements = db.query(Engagement).all()

    matched = [e for e in all_engagements if _match_engagement(e, keywords)] if keywords else []

    accounts = list({e.customer for e in matched if e.customer})
    recent = sorted(matched, key=lambda e: e.id, reverse=True)[:5]

    return CanvasSummary(
        activity=activity,
        engagement_count=len(matched),
        accounts=accounts,
        recent_engagements=[EngagementOut.model_validate(e) for e in recent],
    )
