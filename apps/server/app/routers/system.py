from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..paper_integrations.translator import translation_status
from ..services.dashboard_service import build_dashboard_summary_payload

router = APIRouter()


@router.get("/")
async def root() -> dict:
    return {"name": "RoboResearch Workbench Local API", "ok": True, "translation": translation_status()}


@router.get("/health")
async def health() -> dict:
    return {"ok": True, "translation": translation_status()}


@router.get("/summary")
def summary(db: Session = Depends(get_db)) -> dict:
    tasks_total = db.query(models.Task).count()
    tasks_done = db.query(models.Task).filter(models.Task.status == "done").count()
    paper_counts = db.query(models.Paper.venue, func.count(models.Paper.id)).group_by(models.Paper.venue).all()
    status_counts = {status: db.query(models.Project).filter(func.lower(models.Project.status) == status.lower()).count() for status in schemas.PROJECT_STATUSES}
    return {
        "projects": db.query(models.Project).count(),
        "active_projects": status_counts.get("Active", 0),
        "projects_by_status": status_counts,
        "tasks_total": tasks_total,
        "tasks_done": tasks_done,
        "papers": db.query(models.Paper).count(),
        "reading_notes": db.query(models.ReadingNote).count(),
        "experiments": db.query(models.Experiment).count() + db.query(models.ExperimentStudy).count(),
        "knowledge_links": db.query(models.KnowledgeLink).count(),
        "papers_by_venue": {venue: count for venue, count in paper_counts},
    }


def default_layout() -> list[dict]:
    return [
        {"i": "today", "x": 0, "y": 0, "w": 4, "h": 4},
        {"i": "projects", "x": 4, "y": 0, "w": 4, "h": 4},
        {"i": "papers", "x": 8, "y": 0, "w": 4, "h": 4},
        {"i": "experiments", "x": 0, "y": 4, "w": 4, "h": 4},
        {"i": "capture", "x": 4, "y": 4, "w": 4, "h": 4},
        {"i": "knowledge", "x": 8, "y": 4, "w": 4, "h": 4},
    ]


@router.get("/dashboard/layout", response_model=schemas.DashboardLayoutOut)
def get_dashboard_layout(db: Session = Depends(get_db)) -> dict:
    item = db.get(models.DashboardLayout, "default")
    return {"layout": json.loads(item.layout_json) if item else default_layout()}


@router.put("/dashboard/layout", response_model=schemas.DashboardLayoutOut)
def put_dashboard_layout(payload: schemas.DashboardLayoutIn, db: Session = Depends(get_db)) -> dict:
    item = db.get(models.DashboardLayout, "default")
    if not item:
        item = models.DashboardLayout(id="default")
        db.add(item)
    item.layout_json = json.dumps(payload.layout)
    db.commit()
    return {"layout": payload.layout}


@router.get("/api/dashboard/summary")
def api_dashboard_summary(db: Session = Depends(get_db)) -> dict:
    return build_dashboard_summary_payload(db)
