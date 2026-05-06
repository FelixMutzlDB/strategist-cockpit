"""Canvas router — keyword-matched summaries for each activity slug.

Canvas activity slugs are unique per position on the canvas. Some labels repeat
across the Thought Leadership / Evangelism sections of the canvas (e.g. "Events"),
so each position has its own slug (`events-customer`, `events-evangelism`, ...).
Keyword maps for the duplicate positions intentionally point at the same keyword
set for now; they can diverge later if the UX calls for position-specific views.

SDR-4682 N-6: this surface returned full engagement detail for *all*
strategists' rows. Now scoped to the calling strategist via the same
``strategist_email`` filter as ``/api/engagements`` so tenancy is uniform
across surfaces.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.backend.auth import current_user_email
from src.backend.database import get_db
from src.backend.models import Engagement
from src.backend.schemas import CanvasSummary, EngagementOut

router = APIRouter(prefix="/api/canvas", tags=["canvas"])


# Canonical keyword sets. Reference these from the dispatch map so duplicate
# positions share the same list without duplication.
_KW_EVENTS = ["event", "keynote", "panel", "conference", "community day", "learning day"]
_KW_MARKET_SCOUTING = ["scouting", "research", "trends", "innovation"]
_KW_COMMUNITY_SEEDING = ["community", "meetup", "event", "conference", "DAIS", "DAIWT"]

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
    "individual-coaching": ["coaching", "mentoring", "advising"],
    "strategist-role": ["role", "metrics", "organization"],
    "strategy-cop": ["CoP", "community of practice", "strategy community"],
    "reusable-strategy-assets": ["reusable", "asset", "template", "playbook", "framework"],
    "strategy-research": ["research", "PoV", "point of view", "whitepaper"],
    # Duplicate positions on the canvas map to the same keyword set today.
    "events-customer": _KW_EVENTS,
    "events-evangelism": _KW_EVENTS,
    "market-scouting-customer": _KW_MARKET_SCOUTING,
    "market-scouting-evangelism": _KW_MARKET_SCOUTING,
    "community-seeding-evangelism": _KW_COMMUNITY_SEEDING,
    "community-seeding-thought-leadership": _KW_COMMUNITY_SEEDING,
    # Back-compat: the un-suffixed slugs continue to work so deep links survive
    # the ID refactor.
    "events": _KW_EVENTS,
    "market-scouting": _KW_MARKET_SCOUTING,
    "community-seeding": _KW_COMMUNITY_SEEDING,
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
def get_canvas_summary(
    activity: str,
    db: Session = Depends(get_db),
    user_email: str = Depends(current_user_email),
):
    keywords = CANVAS_ACTIVITY_KEYWORDS.get(activity, [])
    # Tenant filter mirrors /api/engagements (F-TM-1 / N-6). Without this an
    # attacker could read any strategist's engagement details by guessing
    # canvas keywords (vision/CIO/RFP/...).
    all_engagements = (
        db.query(Engagement)
        .filter(Engagement.strategist_email == user_email)
        .all()
    )

    matched = [e for e in all_engagements if _match_engagement(e, keywords)] if keywords else []

    accounts = list({e.customer for e in matched if e.customer})
    recent = sorted(matched, key=lambda e: e.id, reverse=True)[:5]

    return CanvasSummary(
        activity=activity,
        engagement_count=len(matched),
        accounts=accounts,
        recent_engagements=[EngagementOut.model_validate(e) for e in recent],
    )
