"""Pydantic schemas for request/response validation.

Input validation is tightened at the API edge:
- `engagement_type`, `status`, `fy` are Literal enums / regex-constrained
- URL fields must start with http(s)://
- Free-text fields have max_length caps matching the SQLAlchemy columns
- All strings have whitespace stripped before validation
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

EngagementType = Literal["Focus", "One-off", "Customer Event", "Tbc"]
EngagementStatus = Literal[
    "Completed", "Ongoing", "Abandoned", "Not started", "On hold"
]
ProjectCategory = Literal["Presentation", "Application", "Document", "Other"]

# T-212: closed 10-tag enum for qualitative outcomes across all five
# activity categories. Validation lives at the Pydantic edge (Delta has no
# CHECK on array elements). Order is the canonical render order in the UI.
ImpactTag = Literal[
    "blocker_cleared",
    "exec_intro",
    "cxo_engaged",
    "poc_unlocked",
    "competitor_displaced",
    "uco_advanced",
    "product_introduced",
    "roadmap_influenced",
    "evangelism_landed",
    "team_enabled",
]
IMPACT_TAGS: tuple[str, ...] = (
    "blocker_cleared",
    "exec_intro",
    "cxo_engaged",
    "poc_unlocked",
    "competitor_displaced",
    "uco_advanced",
    "product_introduced",
    "roadmap_influenced",
    "evangelism_landed",
    "team_enabled",
)

_FY_PATTERN = r"^FY\d{2}$"
_URL_PATTERN = re.compile(r"^https?://", re.IGNORECASE)


def _validate_optional_url(value: str | None) -> str | None:
    if value is None or value == "":
        return None
    if not _URL_PATTERN.match(value):
        raise ValueError("must be an http(s) URL")
    return value


# --- Engagement Schemas ---
class EngagementBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    engagement_type: EngagementType | None = None
    status: EngagementStatus | None = None
    customer: str | None = Field(default=None, max_length=255)
    engagement_title: str | None = Field(default=None, max_length=500)
    actionable_outcome: str | None = Field(default=None, max_length=4000)
    ae: str | None = Field(default=None, max_length=255)
    asq_url: str | None = Field(default=None, max_length=1000)
    asq_id: str | None = Field(default=None, max_length=100)
    timeframe: str | None = Field(default=None, max_length=255)
    fy: str | None = Field(default=None, pattern=_FY_PATTERN)
    quarter: str | None = Field(default=None, max_length=100)
    related_documents: str | None = Field(default=None, max_length=10000)
    next_steps: str | None = Field(default=None, max_length=10000)
    # Comma-separated Salesforce Use Case Object IDs, e.g. "UCO-1234, UCO-5678".
    uco_ids: str | None = Field(default=None, max_length=500)
    # T-212: qualitative outcome tags stored in the activity_app_data overlay.
    # Closed 10-tag enum; the validator below rejects unknown tags and
    # duplicates (case-sensitive). Empty list is allowed.
    impact_tags: list[ImpactTag] = Field(default_factory=list)
    impact_notes: str | None = Field(default=None, max_length=4000)

    @field_validator("asq_url", mode="before")
    @classmethod
    def _check_asq_url(cls, v: str | None) -> str | None:
        return _validate_optional_url(v)

    @field_validator("impact_tags", mode="before")
    @classmethod
    def _check_impact_tags(cls, v):
        # ``None`` from the wire is normalised to ``[]`` — clients sending
        # ``impact_tags=null`` should not 422.
        if v is None:
            return []
        if not isinstance(v, list):
            raise ValueError("impact_tags must be a list")
        if len(v) != len(set(v)):
            raise ValueError("impact_tags contains duplicate values")
        # Unknown-tag rejection is handled by the Literal type below — this
        # validator only catches duplicates which Pydantic does not.
        return v


class EngagementCreate(EngagementBase):
    customer: str = Field(min_length=1, max_length=255)


class EngagementUpdate(EngagementBase):
    pass


class EngagementOut(EngagementBase):
    model_config = {"from_attributes": True, "str_strip_whitespace": True}
    id: int
    # Read-only tenant key. Never settable via Create/Update — the router
    # stamps it from `current_user_email()` so a client cannot spoof the owner.
    strategist_email: str | None = None


# --- Project Schemas ---
class ProjectBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    url: str = Field(min_length=1, max_length=1000)
    thumbnail_url: str | None = Field(default=None, max_length=1000)
    category: ProjectCategory | None = None

    @field_validator("url", mode="before")
    @classmethod
    def _check_url(cls, v: str) -> str:
        if not _URL_PATTERN.match(v or ""):
            raise ValueError("url must be an http(s) URL")
        return v

    @field_validator("thumbnail_url", mode="before")
    @classmethod
    def _check_thumbnail(cls, v: str | None) -> str | None:
        return _validate_optional_url(v)


class ProjectCreate(ProjectBase):
    pass


class ProjectOut(ProjectBase):
    model_config = {"from_attributes": True, "str_strip_whitespace": True}
    id: int
    created_at: datetime | None = None
    created_by_email: str | None = None


# --- Chat Schemas ---
class ChatMessage(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    message: str = Field(max_length=4000)


class ChatResponse(BaseModel):
    response: str
    source: str = "stratego"


# --- Canvas Schemas ---
class CanvasSummary(BaseModel):
    activity: str
    engagement_count: int
    accounts: list[str]
    recent_engagements: list[EngagementOut]
