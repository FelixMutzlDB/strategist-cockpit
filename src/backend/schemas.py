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
    related_documents: str | None = Field(default=None, max_length=4000)
    next_steps: str | None = Field(default=None, max_length=4000)
    # Comma-separated Salesforce Use Case Object IDs, e.g. "UCO-1234, UCO-5678".
    uco_ids: str | None = Field(default=None, max_length=500)

    @field_validator("asq_url", mode="before")
    @classmethod
    def _check_asq_url(cls, v: str | None) -> str | None:
        return _validate_optional_url(v)


class EngagementCreate(EngagementBase):
    customer: str = Field(min_length=1, max_length=255)


class EngagementUpdate(EngagementBase):
    pass


class EngagementOut(EngagementBase):
    model_config = {"from_attributes": True, "str_strip_whitespace": True}
    id: int


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
