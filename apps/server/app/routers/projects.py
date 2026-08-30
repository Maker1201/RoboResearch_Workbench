from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import crud, git_service, models, project_progress_service, project_scanner_service, schemas
from ..database import get_db
from ..services.projects_service import (
    create_default_stages,
    ensure_project_stages,
    normalize_project_status,
    project_or_404,
    public_project,
)

router = APIRouter()


@router.get("/filesystem/directories")
def list_directories(path: str | None = Query(default=None)) -> dict:
    try:
        return project_scanner_service.list_directories(path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/projects/discover")
def discover_projects() -> list[dict]:
    discovered = []
    for path in sorted(Path("/home/robot").iterdir()):
        if path.is_dir() and not path.name.startswith(".") and (path / ".git").exists():
            discovered.append({"name": path.name, "path": str(path), **git_service.status(str(path))})
    return discovered


@router.get("/projects", response_model=list[schemas.ProjectOut])
def list_projects(search: str | None = None, status: str | None = None, tag: str | None = None, sort: str = "updated", db: Session = Depends(get_db)):
    query = db.query(models.Project)
    if search:
        pattern = f"%{search}%"
        query = query.filter(models.Project.name.ilike(pattern) | models.Project.description.ilike(pattern))
    if status:
        query = query.filter(func.lower(models.Project.status) == status.lower())
    if tag:
        query = query.filter(models.Project.tags.ilike(f"%{tag}%"))
    if sort == "name":
        query = query.order_by(models.Project.name.asc())
    elif sort == "progress":
        query = query.order_by(models.Project.progress.desc())
    else:
        query = query.order_by(models.Project.updated_at.desc())
    projects = query.limit(300).all()
    for project in projects:
        project.status = normalize_project_status(project.status)
        ensure_project_stages(db, project)
        project_progress_service.sync_project_progress(db, project)
    db.commit()
    return projects


@router.post("/projects/refresh-git", response_model=list[schemas.ProjectOut])
def refresh_projects_git(db: Session = Depends(get_db)):
    projects = db.query(models.Project).order_by(models.Project.updated_at.desc()).limit(300).all()
    for project in projects:
        project.status = normalize_project_status(project.status)
        public_project(project)
    db.commit()
    return projects


@router.post("/projects/scan")
def scan_project(payload: schemas.ProjectScanRequest) -> dict:
    try:
        return project_scanner_service.scan_project(payload.path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/projects/register", response_model=schemas.ProjectOut)
def register_project(payload: schemas.ProjectRegisterRequest, db: Session = Depends(get_db)):
    scan = project_scanner_service.scan_project(payload.path)
    existing = db.query(models.Project).filter(models.Project.path == scan["path"]).first()
    if existing:
        return public_project(existing)
    project = models.Project(
        name=payload.name or scan["name"],
        path=scan["path"],
        description=payload.description if payload.description is not None else scan.get("description"),
        status=normalize_project_status(payload.status),
        progress=0,
        progress_mode=payload.progress_mode,
        project_type=scan.get("project_type"),
        tags=payload.tags if payload.tags is not None else ", ".join(scan.get("tags", [])),
        current_stage=(scan.get("suggested_stages") or [{}])[0].get("title"),
        next_stage=(scan.get("suggested_stages") or [{}, {}])[1].get("title") if len(scan.get("suggested_stages") or []) > 1 else None,
        remote_url=scan.get("remote_url"),
        branch=scan.get("branch"),
        default_branch=scan.get("branch") or "main",
    )
    db.add(project)
    db.flush()
    create_default_stages(db, project.id, scan.get("suggested_stages", []))
    db.commit()
    db.refresh(project)
    ensure_project_stages(db, project)
    project_progress_service.sync_project_progress(db, project)
    return public_project(project)


@router.post("/projects", response_model=schemas.ProjectOut)
def create_project(payload: schemas.ProjectCreate, db: Session = Depends(get_db)):
    path = Path(payload.path).expanduser()
    if not path.exists():
        raise HTTPException(status_code=400, detail="Project path does not exist")
    data = payload.model_dump()
    data["status"] = normalize_project_status(data.get("status"))
    project = models.Project(**data)
    db.add(project)
    db.commit()
    db.refresh(project)
    return public_project(project)


@router.patch("/projects/{project_id}", response_model=schemas.ProjectOut)
def update_project(project_id: int, payload: schemas.ProjectUpdate, db: Session = Depends(get_db)):
    if payload.status:
        payload.status = normalize_project_status(payload.status)
    project = crud.update_item(db, models.Project, project_id, payload)
    ensure_project_stages(db, project)
    project_progress_service.sync_project_progress(db, project)
    return public_project(project)


@router.delete("/projects/{project_id}")
def delete_project(project_id: int, db: Session = Depends(get_db)):
    return crud.delete_item(db, models.Project, project_id)


@router.get("/projects/{project_id}/detail")
def project_detail(project_id: int, db: Session = Depends(get_db)) -> dict:
    project = project_or_404(db, project_id)
    project.status = normalize_project_status(project.status)
    ensure_project_stages(db, project)
    project_progress_service.sync_project_progress(db, project)
    project = public_project(project)
    progress = project_progress_service.project_progress(db, project)
    git = git_service.status(project.path)
    experiments = db.query(models.Experiment).filter(models.Experiment.project_id == project.id).order_by(models.Experiment.id.desc()).limit(5).all()
    checkpoints = db.query(models.ProjectCheckpoint).filter(models.ProjectCheckpoint.project_id == project.id).order_by(models.ProjectCheckpoint.id.desc()).limit(20).all()
    return {"project": schemas.ProjectOut.model_validate(project).model_dump(mode="json"), "progress": progress, "git": git, "experiments": [schemas.ExperimentOut.model_validate(item).model_dump(mode="json") for item in experiments], "checkpoints": [schemas.ProjectCheckpointOut.model_validate(item).model_dump(mode="json") for item in checkpoints]}


@router.get("/projects/{project_id}/progress")
def get_project_progress(project_id: int, db: Session = Depends(get_db)) -> dict:
    project = project_or_404(db, project_id)
    ensure_project_stages(db, project)
    project_progress_service.sync_project_progress(db, project)
    return project_progress_service.project_progress(db, project)


@router.post("/projects/{project_id}/progress/initialize")
def initialize_project_progress(project_id: int, db: Session = Depends(get_db)) -> dict:
    project = project_or_404(db, project_id)
    ensure_project_stages(db, project)
    project_progress_service.sync_project_progress(db, project)
    project = public_project(project)
    return {
        "project": schemas.ProjectOut.model_validate(project).model_dump(mode="json"),
        "progress": project_progress_service.project_progress(db, project),
    }


@router.post("/project-stages", response_model=schemas.ProjectStageOut)
def create_stage(payload: schemas.ProjectStageCreate, db: Session = Depends(get_db)):
    stage = crud.create_item(db, models.ProjectStage, payload)
    project_progress_service.sync_project_progress(db, project_or_404(db, stage.project_id))
    return stage


@router.patch("/project-stages/{stage_id}", response_model=schemas.ProjectStageOut)
def update_stage(stage_id: int, payload: schemas.ProjectStageUpdate, db: Session = Depends(get_db)):
    stage = crud.update_item(db, models.ProjectStage, stage_id, payload)
    project_progress_service.sync_project_progress(db, project_or_404(db, stage.project_id))
    return stage


@router.post("/milestones", response_model=schemas.MilestoneOut)
def create_milestone(payload: schemas.MilestoneCreate, db: Session = Depends(get_db)):
    milestone = crud.create_item(db, models.Milestone, payload)
    project_progress_service.sync_project_progress(db, project_or_404(db, milestone.project_id))
    return milestone


@router.patch("/milestones/{milestone_id}", response_model=schemas.MilestoneOut)
def update_milestone(milestone_id: int, payload: schemas.MilestoneUpdate, db: Session = Depends(get_db)):
    milestone = crud.update_item(db, models.Milestone, milestone_id, payload)
    project_progress_service.sync_project_progress(db, project_or_404(db, milestone.project_id))
    return milestone


@router.get("/project-progress")
def list_project_progress(date: str | None = None, project_id: int | None = None, db: Session = Depends(get_db)):
    query = db.query(models.ProjectProgressLog)
    if date:
        query = query.filter(models.ProjectProgressLog.date == date)
    if project_id:
        query = query.filter(models.ProjectProgressLog.project_id == project_id)
    return query.order_by(models.ProjectProgressLog.date.desc(), models.ProjectProgressLog.id.desc()).limit(300).all()


@router.post("/project-progress")
def create_project_progress(payload: dict, db: Session = Depends(get_db)):
    crud.get_item(db, models.Project, payload["project_id"])
    item = models.ProjectProgressLog(**payload)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.patch("/project-progress/{log_id}")
def update_project_progress(log_id: int, payload: dict, db: Session = Depends(get_db)):
    item = crud.get_item(db, models.ProjectProgressLog, log_id)
    for key, value in payload.items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/project-progress/{log_id}")
def delete_project_progress(log_id: int, db: Session = Depends(get_db)):
    return crud.delete_item(db, models.ProjectProgressLog, log_id)
