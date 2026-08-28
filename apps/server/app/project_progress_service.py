from __future__ import annotations

from sqlalchemy.orm import Session

from . import models

DONE_STATUSES = {"done", "completed", "complete"}


def project_progress(db: Session, project: models.Project) -> dict:
    stages = db.query(models.ProjectStage).filter(models.ProjectStage.project_id == project.id).order_by(models.ProjectStage.order_index).all()
    milestones = db.query(models.Milestone).filter(models.Milestone.project_id == project.id).order_by(models.Milestone.order_index).all()
    tasks = db.query(models.Task).filter(models.Task.project_id == project.id).all()
    stage_payload = []
    for stage in stages:
        stage_milestones = [item for item in milestones if item.stage_id == stage.id]
        progress = _weighted_progress([_milestone_payload(item, tasks) for item in stage_milestones]) if stage_milestones else stage.progress
        stage_payload.append({
            "id": stage.id,
            "title": stage.title,
            "status": stage.status,
            "weight": stage.weight,
            "progress": round(progress, 2),
            "order_index": stage.order_index,
            "milestones": [_milestone_payload(item, tasks) for item in stage_milestones],
        })
    orphan_milestones = [_milestone_payload(item, tasks) for item in milestones if item.stage_id is None]
    if project.progress_mode == "MANUAL":
        total = project.progress
    elif stage_payload:
        total = _weighted_progress(stage_payload)
    elif orphan_milestones:
        total = _weighted_progress(orphan_milestones)
    elif tasks:
        total = 100 * len([task for task in tasks if task.status.lower() in DONE_STATUSES]) / len(tasks)
    else:
        total = project.progress
    computed_current = next((stage for stage in stage_payload if stage["progress"] < 100), None)
    computed_next = None
    if computed_current:
        later = [stage for stage in stage_payload if stage["order_index"] > computed_current["order_index"]]
        computed_next = later[0] if later else None
    return {
        "project_id": project.id,
        "mode": project.progress_mode,
        "progress": round(total, 2),
        "current_stage": project.current_stage,
        "next_stage": project.next_stage,
        "computed_current_stage": computed_current["title"] if computed_current else None,
        "computed_next_stage": computed_next["title"] if computed_next else None,
        "stages": stage_payload,
        "orphan_milestones": orphan_milestones,
    }


def sync_project_progress(db: Session, project: models.Project) -> models.Project:
    payload = project_progress(db, project)
    if project.progress_mode != "MANUAL":
        project.progress = payload["progress"]
    db.commit()
    db.refresh(project)
    return project


def _milestone_payload(milestone: models.Milestone, tasks: list[models.Task]) -> dict:
    milestone_tasks = [task for task in tasks if task.milestone_id == milestone.id]
    if milestone_tasks:
        progress = 100 * len([task for task in milestone_tasks if task.status.lower() in DONE_STATUSES]) / len(milestone_tasks)
    else:
        progress = milestone.progress
    return {
        "id": milestone.id,
        "title": milestone.title,
        "status": milestone.status,
        "weight": milestone.weight,
        "progress": round(progress, 2),
        "order_index": milestone.order_index,
        "tasks_total": len(milestone_tasks),
        "tasks_done": len([task for task in milestone_tasks if task.status.lower() in DONE_STATUSES]),
    }


def _weighted_progress(items: list[dict]) -> float:
    if not items:
        return 0
    total_weight = sum(max(float(item.get("weight") or 0), 0) for item in items)
    if total_weight <= 0:
        return sum(float(item.get("progress") or 0) for item in items) / len(items)
    return sum(float(item.get("progress") or 0) * max(float(item.get("weight") or 0), 0) for item in items) / total_weight
