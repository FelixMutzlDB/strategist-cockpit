from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.backend.audit import record_event
from src.backend.auth import current_user_email, current_user_token, is_admin
from src.backend.config import settings
from src.backend.database import get_db
from src.backend.models import Project
from src.backend.repos import projects_repo
from src.backend.schemas import ProjectCreate, ProjectOut

router = APIRouter(prefix="/api/projects", tags=["projects"])


def _use_dbsql() -> bool:
    return settings.data_backend == "dbsql"


@router.get("/", response_model=list[ProjectOut])
def list_projects(
    db: Session = Depends(get_db),
    user_email: str = Depends(current_user_email),
    user_token: str = Depends(current_user_token),
):
    if _use_dbsql():
        rows = projects_repo.list_projects(
            user_token=user_token, strategist_email=user_email
        )
        return [ProjectOut.model_validate(r) for r in rows]
    return db.query(Project).order_by(Project.created_at.desc()).all()


@router.post("/", response_model=ProjectOut, status_code=201)
def create_project(
    project: ProjectCreate,
    db: Session = Depends(get_db),
    user_email: str = Depends(current_user_email),
    user_token: str = Depends(current_user_token),
):
    if _use_dbsql():
        row = projects_repo.create_project(
            user_token=user_token,
            strategist_email=user_email,
            payload=project.model_dump(),
        )
        record_event(
            user_email=user_email,
            action="create",
            target_type="project",
            target_id=row["id"],
        )
        return ProjectOut.model_validate(row)

    db_project = Project(
        **project.model_dump(),
        created_by_email=user_email,
    )
    db.add(db_project)
    db.commit()
    db.refresh(db_project)
    record_event(
        user_email=user_email,
        action="create",
        target_type="project",
        target_id=db_project.id,
    )
    return db_project


@router.delete("/{project_id}", status_code=204)
def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
    user_email: str = Depends(current_user_email),
    user_token: str = Depends(current_user_token),
):
    if _use_dbsql():
        ok = projects_repo.delete_project(
            user_token=user_token,
            strategist_email=user_email,
            project_id=project_id,
        )
        if not ok:
            record_event(
                user_email=user_email,
                action="delete",
                target_type="project",
                target_id=project_id,
                result="forbidden_or_missing",
            )
            raise HTTPException(status_code=404, detail="Project not found")
        record_event(
            user_email=user_email,
            action="delete",
            target_type="project",
            target_id=project_id,
        )
        return

    project = db.query(Project).filter(Project.id == project_id).first()
    # Treat both "not found" and "not yours" as 404 to avoid leaking existence
    # to non-owners — per SDR-4682 F-TM-5 reviewer guidance.
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    is_owner = (project.created_by_email or "").lower() == user_email.lower()
    if not (is_owner or is_admin(user_email)):
        record_event(
            user_email=user_email,
            action="delete",
            target_type="project",
            target_id=project_id,
            result="forbidden",
        )
        raise HTTPException(status_code=404, detail="Project not found")
    db.delete(project)
    db.commit()
    record_event(
        user_email=user_email,
        action="delete",
        target_type="project",
        target_id=project_id,
    )
