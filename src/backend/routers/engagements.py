from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from src.backend.audit import record_event
from src.backend.auth import current_user_email, current_user_token
from src.backend.config import settings
from src.backend.database import get_db
from src.backend.models import Engagement
from src.backend.repos import customer_engagements_repo as engagements_repo
from src.backend.schemas import EngagementCreate, EngagementOut, EngagementUpdate

router = APIRouter(prefix="/api/engagements", tags=["engagements"])


def _use_dbsql() -> bool:
    return settings.data_backend == "dbsql"


@router.get("/", response_model=list[EngagementOut])
def list_engagements(
    fy: str | None = Query(None, description="Filter by fiscal year, e.g. FY26"),
    engagement_type: str | None = Query(None, description="Filter by type: Focus, One-off, Customer Event"),
    status: str | None = Query(None, description="Filter by status: Completed, Ongoing, etc."),
    customer: str | None = Query(None, description="Filter by customer name (partial match)"),
    db: Session = Depends(get_db),
    user_email: str = Depends(current_user_email),
    user_token: str = Depends(current_user_token),
):
    if _use_dbsql():
        rows = engagements_repo.list_engagements(
            user_token=user_token,
            strategist_email=user_email,
            filters={
                "fy": fy,
                "engagement_type": engagement_type,
                "status": status,
                "customer": customer,
            },
        )
        return [EngagementOut.model_validate(r) for r in rows]

    # F-TM-1 SQLite path: tenant filter must be the FIRST clause so any
    # accidental future predicate change can't loosen scoping.
    query = db.query(Engagement).filter(Engagement.strategist_email == user_email)
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
def get_engagement(
    engagement_id: int,
    db: Session = Depends(get_db),
    user_email: str = Depends(current_user_email),
    user_token: str = Depends(current_user_token),
):
    if _use_dbsql():
        row = engagements_repo.get_engagement(
            user_token=user_token,
            strategist_email=user_email,
            engagement_id=engagement_id,
        )
        if row is None:
            raise HTTPException(status_code=404, detail="Engagement not found")
        return EngagementOut.model_validate(row)

    eng = (
        db.query(Engagement)
        .filter(
            Engagement.id == engagement_id,
            Engagement.strategist_email == user_email,
        )
        .first()
    )
    if not eng:
        raise HTTPException(status_code=404, detail="Engagement not found")
    return eng


@router.post("/", response_model=EngagementOut, status_code=201)
def create_engagement(
    engagement: EngagementCreate,
    db: Session = Depends(get_db),
    user_email: str = Depends(current_user_email),
    user_token: str = Depends(current_user_token),
):
    if _use_dbsql():
        row = engagements_repo.create_engagement(
            user_token=user_token,
            strategist_email=user_email,
            payload=engagement.model_dump(),
        )
        record_event(
            user_email=user_email,
            action="create",
            target_type="engagement",
            target_id=row["id"],
            user_token=user_token,
        )
        return EngagementOut.model_validate(row)

    # Tenant key is stamped from the auth dep, never the payload (F-TM-1).
    db_engagement = Engagement(
        **engagement.model_dump(),
        strategist_email=user_email,
    )
    db.add(db_engagement)
    db.commit()
    db.refresh(db_engagement)
    record_event(
        user_email=user_email,
        action="create",
        target_type="engagement",
        target_id=db_engagement.id,
        user_token=user_token,
    )
    return db_engagement


@router.put("/{engagement_id}", response_model=EngagementOut)
def update_engagement(
    engagement_id: int,
    engagement: EngagementUpdate,
    db: Session = Depends(get_db),
    user_email: str = Depends(current_user_email),
    user_token: str = Depends(current_user_token),
):
    if _use_dbsql():
        update_data = engagement.model_dump(exclude_unset=True)
        row = engagements_repo.update_engagement(
            user_token=user_token,
            strategist_email=user_email,
            engagement_id=engagement_id,
            payload=update_data,
        )
        if row is None:
            raise HTTPException(status_code=404, detail="Engagement not found")
        record_event(
            user_email=user_email,
            action="update",
            target_type="engagement",
            target_id=engagement_id,
            user_token=user_token,
        )
        return EngagementOut.model_validate(row)

    db_engagement = (
        db.query(Engagement)
        .filter(
            Engagement.id == engagement_id,
            Engagement.strategist_email == user_email,
        )
        .first()
    )
    if not db_engagement:
        raise HTTPException(status_code=404, detail="Engagement not found")
    update_data = engagement.model_dump(exclude_unset=True)
    # Defence-in-depth: never let an Update payload re-stamp the tenant.
    update_data.pop("strategist_email", None)
    for key, value in update_data.items():
        setattr(db_engagement, key, value)
    db.commit()
    db.refresh(db_engagement)
    record_event(
        user_email=user_email,
        action="update",
        target_type="engagement",
        target_id=engagement_id,
        user_token=user_token,
    )
    return db_engagement


@router.delete("/{engagement_id}", status_code=204)
def delete_engagement(
    engagement_id: int,
    db: Session = Depends(get_db),
    user_email: str = Depends(current_user_email),
    user_token: str = Depends(current_user_token),
):
    if _use_dbsql():
        existing = engagements_repo.get_engagement(
            user_token=user_token,
            strategist_email=user_email,
            engagement_id=engagement_id,
        )
        if existing is None:
            raise HTTPException(status_code=404, detail="Engagement not found")
        engagements_repo.delete_engagement(
            user_token=user_token,
            strategist_email=user_email,
            engagement_id=engagement_id,
        )
        record_event(
            user_email=user_email,
            action="delete",
            target_type="engagement",
            target_id=engagement_id,
            user_token=user_token,
        )
        return

    db_engagement = (
        db.query(Engagement)
        .filter(
            Engagement.id == engagement_id,
            Engagement.strategist_email == user_email,
        )
        .first()
    )
    if not db_engagement:
        raise HTTPException(status_code=404, detail="Engagement not found")
    db.delete(db_engagement)
    db.commit()
    record_event(
        user_email=user_email,
        action="delete",
        target_type="engagement",
        target_id=engagement_id,
        user_token=user_token,
    )
