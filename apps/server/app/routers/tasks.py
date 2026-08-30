from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import crud, models, project_progress_service, schemas
from ..database import get_db
from ..services.projects_service import project_or_404

router = APIRouter()


@router.get("/tasks", response_model=list[schemas.TaskOut])
def list_tasks(db: Session = Depends(get_db)):
    return crud.list_items(db, models.Task)


@router.post("/tasks", response_model=schemas.TaskOut)
def create_task(payload: schemas.TaskCreate, db: Session = Depends(get_db)):
    task = crud.create_item(db, models.Task, payload)
    if task.project_id:
        project_progress_service.sync_project_progress(db, project_or_404(db, task.project_id))
    return task


@router.patch("/tasks/{task_id}", response_model=schemas.TaskOut)
def update_task(task_id: int, payload: schemas.TaskUpdate, db: Session = Depends(get_db)):
    task = crud.update_item(db, models.Task, task_id, payload)
    if task.project_id:
        project_progress_service.sync_project_progress(db, project_or_404(db, task.project_id))
    return task


@router.delete("/tasks/{task_id}")
def delete_task(task_id: int, db: Session = Depends(get_db)):
    task = db.get(models.Task, task_id)
    project_id = task.project_id if task else None
    result = crud.delete_item(db, models.Task, task_id)
    if project_id:
        project_progress_service.sync_project_progress(db, project_or_404(db, project_id))
    return result
