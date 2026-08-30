from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .. import crud, git_service, models, project_scanner_service, schemas


def normalize_project_status(value: str | None) -> str:
    if not value:
        return "Active"
    mapping = {item.lower(): item for item in schemas.PROJECT_STATUSES}
    return mapping.get(value.lower(), value)


def create_default_stages(db: Session, project_id: int, stages: list[dict[str, Any]]) -> None:
    if db.query(models.ProjectStage).filter(models.ProjectStage.project_id == project_id).count():
        return
    for stage in stages:
        db.add(models.ProjectStage(project_id=project_id, **stage))


def ensure_project_stages(db: Session, project: models.Project) -> None:
    stages = db.query(models.ProjectStage).filter(models.ProjectStage.project_id == project.id).order_by(models.ProjectStage.order_index).all()
    if not stages:
        try:
            scan = project_scanner_service.scan_project(project.path)
            suggested = scan.get("suggested_stages", [])
        except Exception:
            suggested = project_scanner_service.default_stages(project.project_type or "Research Project")
        if not suggested:
            suggested = project_scanner_service.default_stages(project.project_type or "Research Project")
        create_default_stages(db, project.id, suggested)
        stages = db.query(models.ProjectStage).filter(models.ProjectStage.project_id == project.id).order_by(models.ProjectStage.order_index).all()

    empty_values = {None, "", "无", "未设置", "none", "None"}
    if stages and project.current_stage in empty_values:
        project.current_stage = stages[0].title
    if len(stages) > 1 and project.next_stage in empty_values:
        project.next_stage = stages[1].title
    db.flush()


def project_or_404(db: Session, project_id: int) -> models.Project:
    return crud.get_item(db, models.Project, project_id)


def project_health(path: str, status_value: str | None) -> str:
    if status_value == "Blocked":
        return "Blocked"
    git = git_service.status(path)
    if not git.get("is_repo") or not git.get("remote_url") or git.get("changes") or git.get("unpushed_commits"):
        return "Needs Attention"
    if not any(child.name.lower().startswith("readme") for child in Path(path).iterdir() if child.is_file()):
        return "Needs Attention"
    return "Healthy"


def public_project(project: models.Project) -> models.Project:
    try:
        git = git_service.status(project.path)
        project.branch = git.get("branch") or project.branch
        project.remote_url = git.get("remote_url") or project.remote_url
        project.health = project_health(project.path, project.status)
    except Exception:
        project.health = "Needs Attention"
    return project
