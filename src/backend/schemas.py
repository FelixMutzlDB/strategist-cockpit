from pydantic import BaseModel
from datetime import datetime
from typing import Optional


# --- Engagement Schemas ---
class EngagementBase(BaseModel):
    engagement_type: Optional[str] = None
    status: Optional[str] = None
    customer: Optional[str] = None
    engagement_title: Optional[str] = None
    actionable_outcome: Optional[str] = None
    ae: Optional[str] = None
    asq_url: Optional[str] = None
    asq_id: Optional[str] = None
    timeframe: Optional[str] = None
    fy: Optional[str] = None
    quarter: Optional[str] = None
    related_documents: Optional[str] = None
    next_steps: Optional[str] = None


class EngagementCreate(EngagementBase):
    customer: str


class EngagementOut(EngagementBase):
    id: int

    class Config:
        from_attributes = True


# --- Project Schemas ---
class ProjectBase(BaseModel):
    name: str
    description: Optional[str] = None
    url: str
    thumbnail_url: Optional[str] = None
    category: Optional[str] = None


class ProjectCreate(ProjectBase):
    pass


class ProjectOut(ProjectBase):
    id: int
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# --- Chat Schemas ---
class ChatMessage(BaseModel):
    message: str


class ChatResponse(BaseModel):
    response: str
    source: str = "stratego"


# --- Canvas Schemas ---
class CanvasSummary(BaseModel):
    activity: str
    engagement_count: int
    accounts: list[str]
    recent_engagements: list[EngagementOut]
