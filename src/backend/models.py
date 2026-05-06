from sqlalchemy import Column, DateTime, Integer, String, Text, func

from src.backend.database import Base


class Engagement(Base):
    __tablename__ = "engagements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    engagement_type = Column(String(50))  # Focus, One-off, Customer Event, Tbc
    status = Column(String(50))  # Completed, Ongoing, Abandoned, Not started, On hold
    customer = Column(String(255))
    engagement_title = Column(String(500))
    actionable_outcome = Column(Text)
    ae = Column(String(255))  # Account Executive
    asq_url = Column(String(1000))
    asq_id = Column(String(100))
    timeframe = Column(String(255))
    fy = Column(String(10))  # FY25, FY26, FY27
    quarter = Column(String(100))
    related_documents = Column(Text)
    next_steps = Column(Text)
    # Comma-separated Salesforce Use Case Object IDs, e.g. "UCO-1234, UCO-5678".
    uco_ids = Column(String(500))
    # Tenant key (F-TM-1 / SDR-4682 N-6). Stamped from `current_user_email()`
    # on every write. Every read filters by it. Same shape as `Project.created_by_email`.
    strategist_email = Column(String(255), index=True)


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    url = Column(String(1000), nullable=False)
    thumbnail_url = Column(String(1000))
    category = Column(String(100))
    created_at = Column(DateTime, server_default=func.now())
    # Email of the user who created the project (from X-Forwarded-Email).
    # DELETE is gated to creator-or-admin (T-208 / SDR F-TM-5).
    created_by_email = Column(String(255), index=True)
