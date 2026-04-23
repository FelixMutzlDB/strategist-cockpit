from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import Optional

from src.backend.database import get_db
from src.backend.models import Engagement
from src.backend.schemas import EngagementOut, EngagementCreate, EngagementUpdate

router = APIRouter(prefix="/api/engagements", tags=["engagements"])


@router.get("/", response_model=list[EngagementOut])
def list_engagements(
    fy: Optional[str] = Query(None, description="Filter by fiscal year, e.g. FY26"),
    engagement_type: Optional[str] = Query(None, description="Filter by type: Focus, One-off, Customer Event"),
    status: Optional[str] = Query(None, description="Filter by status: Completed, Ongoing, etc."),
    customer: Optional[str] = Query(None, description="Filter by customer name (partial match)"),
    db: Session = Depends(get_db),
):
    query = db.query(Engagement)
    if fy:
        query = query.filter(Engagement.fy == fy)
    if engagement_type:
        query = query.filter(Engagement.engagement_type == engagement_type)
    if status:
        query = query.filter(Engagement.status == status)
    if customer:
        query = query.filter(Engagement.customer.ilike(f"%{customer}%"))
    return query.order_by(Engagement.id.desc()).all()


@router.get("/{engagement_id}", response_model=EngagementOut)
def get_engagement(engagement_id: int, db: Session = Depends(get_db)):
    eng = db.query(Engagement).filter(Engagement.id == engagement_id).first()
    if not eng:
        raise HTTPException(status_code=404, detail="Engagement not found")
    return eng


@router.post("/", response_model=EngagementOut, status_code=201)
def create_engagement(engagement: EngagementCreate, db: Session = Depends(get_db)):
    db_engagement = Engagement(**engagement.model_dump())
    db.add(db_engagement)
    db.commit()
    db.refresh(db_engagement)
    return db_engagement


@router.put("/{engagement_id}", response_model=EngagementOut)
def update_engagement(
    engagement_id: int,
    engagement: EngagementUpdate,
    db: Session = Depends(get_db),
):
    db_engagement = db.query(Engagement).filter(Engagement.id == engagement_id).first()
    if not db_engagement:
        raise HTTPException(status_code=404, detail="Engagement not found")
    update_data = engagement.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_engagement, key, value)
    db.commit()
    db.refresh(db_engagement)
    return db_engagement


@router.delete("/{engagement_id}", status_code=204)
def delete_engagement(engagement_id: int, db: Session = Depends(get_db)):
    db_engagement = db.query(Engagement).filter(Engagement.id == engagement_id).first()
    if not db_engagement:
        raise HTTPException(status_code=404, detail="Engagement not found")
    db.delete(db_engagement)
    db.commit()
