from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from .. import models, project_progress_service, schemas
from .papers_service import normalize_paper_status
from .settings_service import build_settings_payload

PROJECT_STATUSES_LOWER = ["planning", "active", "blocked", "paused", "completed", "archived"]
PAPER_STATUSES = ["Inbox", "Candidate", "To Read", "Skimming", "Reading", "Deep Reading", "Finished", "Reference", "Dropped"]
EXPERIMENT_STATUSES = ["running", "pending", "completed", "failed"]
DASHBOARD_VENUES = ["ICRA", "IROS", "RA-L", "T-RO", "Science Robotics"]


def focus_elapsed_seconds(session: models.FocusSession, now: datetime | None = None) -> int:
    now = now or datetime.utcnow()
    if session.status in {"COMPLETED", "CANCELLED"}:
        return session.duration_seconds
    paused_seconds = session.paused_seconds
    if session.status == "PAUSED" and session.paused_started_at:
        paused_seconds += max(0, int((now - session.paused_started_at).total_seconds()))
    return max(0, int((now - session.started_at).total_seconds()) - paused_seconds)


def focus_out(session: models.FocusSession | None) -> dict[str, Any] | None:
    if not session:
        return None
    return {
        "id": session.id,
        "started_at": session.started_at.isoformat(),
        "ended_at": session.ended_at.isoformat() if session.ended_at else None,
        "duration_seconds": session.duration_seconds,
        "paused_seconds": session.paused_seconds,
        "status": session.status,
        "focus_type": session.focus_type,
        "context_type": session.context_type,
        "task_id": session.task_id,
        "project_id": session.project_id,
        "paper_id": session.paper_id,
        "reading_note_id": session.reading_note_id,
        "note": session.note,
        "created_at": session.created_at.isoformat(),
        "updated_at": session.updated_at.isoformat(),
        "elapsed_seconds": focus_elapsed_seconds(session),
        "task_title": session.task.title if session.task else None,
        "project_name": session.project.name if session.project else None,
        "paper_title": session.paper.title if session.paper else None,
        "reading_note_title": session.reading_note.title if session.reading_note else None,
    }


def current_focus_session(db: Session) -> models.FocusSession | None:
    return db.query(models.FocusSession).filter(models.FocusSession.status.in_(["RUNNING", "PAUSED"])).order_by(models.FocusSession.id.desc()).first()


def focus_range_start(range_name: str) -> datetime:
    now = datetime.utcnow()
    start = datetime(now.year, now.month, now.day)
    if range_name == "week":
        return start - timedelta(days=start.weekday())
    if range_name == "month":
        return datetime(now.year, now.month, 1)
    return start


def focus_duration_for_range(db: Session, range_name: str) -> int:
    start = focus_range_start(range_name)
    sessions = db.query(models.FocusSession).filter(models.FocusSession.started_at >= start).all()
    return sum(focus_elapsed_seconds(session) for session in sessions if session.status != "CANCELLED")


def infer_experiment_status(experiment: models.Experiment) -> str:
    text_value = f"{experiment.result or ''} {experiment.conclusion or ''}".lower()
    if any(word in text_value for word in ["fail", "failed", "error", "失败"]):
        return "failed"
    if experiment.conclusion:
        return "completed"
    if experiment.result:
        return "running"
    return "pending"


def build_dashboard_summary_payload(db: Session) -> dict[str, Any]:
    today = datetime.utcnow().strftime("%Y-%m-%d")
    today_tasks = db.query(models.Task).filter((models.Task.due_date == today) | (models.Task.due_date.is_(None))).order_by(models.Task.id.desc()).limit(12).all()
    projects = db.query(models.Project).order_by(models.Project.updated_at.desc()).all()
    project_counts = {status: 0 for status in PROJECT_STATUSES_LOWER}
    featured = []
    for project in projects:
        status_key = (project.status or "active").lower()
        if status_key in project_counts:
            project_counts[status_key] += 1
        progress = project_progress_service.project_progress(db, project)
        featured.append({"id": project.id, "name": project.name, "status": status_key, "progress": progress["progress"], "current_milestone": project.current_stage or progress.get("computed_current_stage"), "next_milestone": project.next_stage or progress.get("computed_next_stage")})
    papers = db.query(models.Paper).order_by(models.Paper.updated_at.desc()).all()
    paper_status_counts = {status: 0 for status in PAPER_STATUSES}
    venue_counts = {venue: 0 for venue in DASHBOARD_VENUES}
    currently_reading = []
    recently_finished = []
    for paper in papers:
        status = normalize_paper_status(paper.status)
        paper_status_counts[status] = paper_status_counts.get(status, 0) + 1
        if paper.venue in venue_counts:
            venue_counts[paper.venue] += 1
        if status in {"Skimming", "Reading", "Deep Reading"}:
            currently_reading.append({"id": paper.id, "title": paper.title, "venue": paper.venue, "year": paper.year})
        if status in {"Finished", "Reference"}:
            recently_finished.append({"id": paper.id, "title": paper.title, "venue": paper.venue, "year": paper.year})
    experiments = db.query(models.Experiment).order_by(models.Experiment.updated_at.desc()).all()
    experiment_studies = db.query(models.ExperimentStudy).order_by(models.ExperimentStudy.updated_at.desc()).all()
    experiment_counts = {status: 0 for status in EXPERIMENT_STATUSES}
    for experiment in experiments:
        experiment_counts[infer_experiment_status(experiment)] += 1
    for study in experiment_studies:
        status = (study.status or "pending").lower()
        if status == "planning":
            status = "pending"
        if status in experiment_counts:
            experiment_counts[status] += 1
    settings_payload = build_settings_payload(db)
    current_session = current_focus_session(db)
    return {
        "today": {"date": today, "tasks": [schemas.TaskOut.model_validate(task).model_dump(mode="json") for task in today_tasks], "completed_tasks": sum(1 for task in today_tasks if task.status == "done"), "total_tasks": len(today_tasks), "completion_rate": 0, "courses": [], "schedule": [], "plan": [task.title for task in today_tasks if task.status != "done"][:5]},
        "projects": {"total": len(projects), "counts": project_counts, "featured": featured[:6]},
        "papers": {"total": len(papers), "status_counts": paper_status_counts, "venue_counts": venue_counts, "currently_reading": currently_reading[:6], "recently_finished": recently_finished[:6]},
        "experiments": {"total": len(experiments) + len(experiment_studies), "counts": experiment_counts, "running": [{"id": study.id, "code": study.study_code, "title": study.name, "metrics": study.claim, "conclusion": study.hypothesis_status} for study in experiment_studies if (study.status or "").lower() == "running"][:6], "recent_results": [{"id": study.id, "code": study.study_code, "title": study.name, "metrics": study.evidence_summary, "conclusion": study.hypothesis_status} for study in experiment_studies if (study.status or "").lower() == "completed"][:6], "research_ideas_pending": db.query(models.ResearchIdea).filter(models.ResearchIdea.status == "candidate").count(), "research_ideas": []},
        "knowledge": {"obsidian_connected": bool(settings_payload["integrations"]["obsidian"]["enabled"] and settings_payload["integrations"]["obsidian"]["vault_path"]), "total_notes": db.query(models.KnowledgeLink).count(), "updated_this_week": 0, "recently_updated": []},
        "git": {"projects": []},
        "focus": {"current_session": focus_out(current_session), "today_duration": focus_duration_for_range(db, "today"), "week_duration": focus_duration_for_range(db, "week")},
        "attention": [],
    }
