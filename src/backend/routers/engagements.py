from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from src.backend.audit import record_event
from src.backend.auth import current_user_email, current_user_token
from src.backend.config import settings
from src.backend.database import get_db
from src.backend.models import Engagement
from src.backend.repos import activity_overlay_repo
from src.backend.repos import customer_engagements_repo as engagements_repo
from src.backend.schemas import EngagementCreate, EngagementOut, EngagementUpdate

router = APIRouter(prefix="/api/engagements", tags=["engagements"])

# T-212: fields routed to the overlay table, not the engagements table.
_OVERLAY_FIELDS = ("impact_tags", "impact_notes")


def _use_dbsql() -> bool:
    return settings.data_backend == "dbsql"


def _sqlite_overlay_key(eng: Engagement) -> str:
    """Stable overlay key for a SQLAlchemy engagement row.

    Mirrors ``activity_overlay_repo.customer_engagement_key`` but operates
    on the ORM object instead of a dict.
    """
    if eng.asq_id:
        return f"asq:{eng.asq_id}"
    return f"manual:{eng.id}"


def _attach_sqlite_overlay(db: Session, eng: Engagement, user_email: str) -> Engagement:
    """Populate ``impact_tags`` / ``impact_notes`` on the ORM object from the overlay.

    Pydantic ``EngagementOut`` reads these as plain attributes; setting them
    on the SQLAlchemy instance keeps the response surface identical to the
    DBSQL path.
    """
    overlay = activity_overlay_repo.get_tags_sqlite(
        db,
        category="customer",
        activity_key=_sqlite_overlay_key(eng),
        strategist_email=user_email,
    )
    # ``setattr`` on a SQLAlchemy ORM instance is fine for non-mapped attrs —
    # they're shed when the response is serialised.
    eng.impact_tags = overlay["impact_tags"] if overlay else []  # type: ignore[attr-defined]
    eng.impact_notes = overlay["impact_notes"] if overlay else None  # type: ignore[attr-defined]
    return eng


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
    rows = query.order_by(Engagement.id.desc()).all()
    for eng in rows:
        _attach_sqlite_overlay(db, eng, user_email)
    return rows


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
    return _attach_sqlite_overlay(db, eng, user_email)


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
    # T-212: split overlay-bound fields out before constructing the ORM row —
    # they live in ``activity_overlay`` (SQLite mirror of activity_app_data).
    payload = engagement.model_dump()
    overlay_tags = payload.pop("impact_tags", []) or []
    overlay_notes = payload.pop("impact_notes", None)
    db_engagement = Engagement(
        **payload,
        strategist_email=user_email,
    )
    db.add(db_engagement)
    db.commit()
    db.refresh(db_engagement)
    if overlay_tags or overlay_notes:
        activity_overlay_repo.set_tags_sqlite(
            db,
            category="customer",
            activity_key=_sqlite_overlay_key(db_engagement),
            strategist_email=user_email,
            tags=overlay_tags,
            notes=overlay_notes,
        )
    record_event(
        user_email=user_email,
        action="create",
        target_type="engagement",
        target_id=db_engagement.id,
        user_token=user_token,
    )
    return _attach_sqlite_overlay(db, db_engagement, user_email)


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
    # T-212: route overlay fields to activity_overlay, not the ORM row.
    overlay_payload = {
        k: update_data.pop(k) for k in list(_OVERLAY_FIELDS) if k in update_data
    }
    for key, value in update_data.items():
        setattr(db_engagement, key, value)
    db.commit()
    db.refresh(db_engagement)
    if overlay_payload:
        existing = activity_overlay_repo.get_tags_sqlite(
            db,
            category="customer",
            activity_key=_sqlite_overlay_key(db_engagement),
            strategist_email=user_email,
        ) or {"impact_tags": [], "impact_notes": None}
        new_tags = overlay_payload.get("impact_tags", existing["impact_tags"]) or []
        new_notes = overlay_payload.get("impact_notes", existing["impact_notes"])
        activity_overlay_repo.set_tags_sqlite(
            db,
            category="customer",
            activity_key=_sqlite_overlay_key(db_engagement),
            strategist_email=user_email,
            tags=new_tags,
            notes=new_notes,
        )
    record_event(
        user_email=user_email,
        action="update",
        target_type="engagement",
        target_id=engagement_id,
        user_token=user_token,
    )
    return _attach_sqlite_overlay(db, db_engagement, user_email)


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
