from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import crud, models, schemas
from ..database import get_db
from ..services.dashboard_service import (
    current_focus_session,
    focus_duration_for_range,
    focus_elapsed_seconds,
    focus_out,
)

router = APIRouter()


@router.get("/experiments", response_model=list[schemas.ExperimentOut])
def list_experiments(db: Session = Depends(get_db)):
    return crud.list_items(db, models.Experiment)


@router.post("/experiments", response_model=schemas.ExperimentOut)
def create_experiment(payload: schemas.ExperimentCreate, db: Session = Depends(get_db)):
    return crud.create_item(db, models.Experiment, payload)


@router.patch("/experiments/{experiment_id}", response_model=schemas.ExperimentOut)
def update_experiment(experiment_id: int, payload: schemas.ExperimentUpdate, db: Session = Depends(get_db)):
    return crud.update_item(db, models.Experiment, experiment_id, payload)


@router.delete("/experiments/{experiment_id}")
def delete_experiment(experiment_id: int, db: Session = Depends(get_db)):
    return crud.delete_item(db, models.Experiment, experiment_id)


@router.get("/knowledge-links", response_model=list[schemas.KnowledgeLinkOut])
def list_knowledge_links(db: Session = Depends(get_db)):
    return crud.list_items(db, models.KnowledgeLink)


@router.post("/knowledge-links", response_model=schemas.KnowledgeLinkOut)
def create_knowledge_link(payload: schemas.KnowledgeLinkCreate, db: Session = Depends(get_db)):
    return crud.create_item(db, models.KnowledgeLink, payload)


@router.patch("/knowledge-links/{knowledge_id}", response_model=schemas.KnowledgeLinkOut)
def update_knowledge_link(knowledge_id: int, payload: schemas.KnowledgeLinkUpdate, db: Session = Depends(get_db)):
    return crud.update_item(db, models.KnowledgeLink, knowledge_id, payload)


@router.delete("/knowledge-links/{knowledge_id}")
def delete_knowledge_link(knowledge_id: int, db: Session = Depends(get_db)):
    return crud.delete_item(db, models.KnowledgeLink, knowledge_id)


@router.get("/api/focus/current")
def api_get_current_focus(db: Session = Depends(get_db)) -> dict:
    return {"current_session": focus_out(current_focus_session(db))}


@router.post("/api/focus/start")
def api_start_focus(payload: dict, db: Session = Depends(get_db)) -> dict:
    if current_focus_session(db):
        raise HTTPException(status_code=409, detail="A focus session is already running or paused")
    task_id = payload.get("task_id")
    project_id = payload.get("project_id")
    paper_id = payload.get("paper_id")
    reading_note_id = payload.get("reading_note_id")
    if task_id is not None:
        crud.get_item(db, models.Task, task_id)
    if project_id is not None:
        crud.get_item(db, models.Project, project_id)
    if paper_id is not None:
        paper = crud.get_item(db, models.Paper, paper_id)
        if project_id is None:
            project_id = paper.related_project_id
    if reading_note_id is not None:
        note = crud.get_item(db, models.ReadingNote, reading_note_id)
        if paper_id is None:
            paper_id = note.paper_id
        if project_id is None:
            project_id = note.related_project_id
    context_type = payload.get("context_type") or ("PAPER_READING" if paper_id or reading_note_id else None)
    session = models.FocusSession(
        task_id=task_id,
        project_id=project_id,
        paper_id=paper_id,
        reading_note_id=reading_note_id,
        focus_type=payload.get("focus_type") or context_type,
        context_type=context_type,
        note=payload.get("note"),
        status="RUNNING",
        started_at=datetime.utcnow(),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return focus_out(session)


@router.post("/api/focus/{session_id}/pause")
def api_pause_focus(session_id: int, db: Session = Depends(get_db)) -> dict:
    session = crud.get_item(db, models.FocusSession, session_id)
    if session.status != "RUNNING":
        raise HTTPException(status_code=400, detail="Only a running focus session can be paused")
    session.status = "PAUSED"
    session.paused_started_at = datetime.utcnow()
    db.commit()
    db.refresh(session)
    return focus_out(session)


@router.post("/api/focus/{session_id}/resume")
def api_resume_focus(session_id: int, db: Session = Depends(get_db)) -> dict:
    session = crud.get_item(db, models.FocusSession, session_id)
    if session.status != "PAUSED":
        raise HTTPException(status_code=400, detail="Only a paused focus session can be resumed")
    now = datetime.utcnow()
    if session.paused_started_at:
        session.paused_seconds += max(0, int((now - session.paused_started_at).total_seconds()))
    session.paused_started_at = None
    session.status = "RUNNING"
    db.commit()
    db.refresh(session)
    return focus_out(session)


@router.post("/api/focus/{session_id}/finish")
def api_finish_focus(session_id: int, db: Session = Depends(get_db)) -> dict:
    session = crud.get_item(db, models.FocusSession, session_id)
    if session.status not in {"RUNNING", "PAUSED"}:
        raise HTTPException(status_code=400, detail="Only an active focus session can be finished")
    now = datetime.utcnow()
    session.duration_seconds = focus_elapsed_seconds(session, now)
    if session.status == "PAUSED" and session.paused_started_at:
        session.paused_seconds += max(0, int((now - session.paused_started_at).total_seconds()))
        session.paused_started_at = None
    session.status = "COMPLETED"
    session.ended_at = now
    db.commit()
    db.refresh(session)
    return focus_out(session)


@router.get("/api/focus/stats")
def api_focus_stats(range: str = "today", db: Session = Depends(get_db)) -> dict:
    if range not in {"today", "week", "month"}:
        raise HTTPException(status_code=400, detail="Unsupported range")
    return {"range": range, "duration_seconds": focus_duration_for_range(db, range)}
