from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func
from sqlalchemy.orm import Session

from . import crud, git_service, models, schemas
from .database import Base, engine, get_db
from .paper_integrations.crossref import search_crossref
from .paper_integrations.models import SearchRequest, SearchResponse, ZoteroAttachPdfRequest, ZoteroImportRequest
from .paper_integrations.openalex import search_openalex
from .paper_integrations.translator import translate_papers, translation_status
from .paper_integrations.zotero import attach_pdf_to_zotero, import_to_zotero, zotero_status

app = FastAPI(title="RoboResearch Workbench Local API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[],
    allow_origin_regex=r"(moz-extension://.*|http://127\.0\.0\.1(:\d+)?|http://localhost(:\d+)?)",
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    Base.metadata.create_all(bind=engine)
    seed_defaults()


def seed_defaults() -> None:
    db = next(get_db())
    try:
        if db.query(models.Project).count() == 0:
            for name in ["IsaacLab", "LLM-as-BT-Planner", "Hrs_loco_manipulation", "DRL_robot_navigation_ros2"]:
                path = Path("/home/robot") / name
                if path.exists():
                    status = git_service.status(str(path)) if (path / ".git").exists() else {}
                    db.add(models.Project(
                        name=name,
                        path=str(path),
                        description="Imported from /home/robot for local research management.",
                        progress=0,
                        remote_url=status.get("remote_url"),
                        branch=status.get("branch"),
                    ))
        if db.query(models.Task).count() == 0:
            db.add_all([
                models.Task(title="精读一篇 VLA / Manipulation 论文", priority="high", status="todo"),
                models.Task(title="整理本周实验记录", priority="high", status="todo"),
                models.Task(title="检查本地项目 Git 状态", priority="medium", status="todo"),
            ])
        if db.query(models.KnowledgeLink).count() == 0:
            db.add_all([
                models.KnowledgeLink(title="VLA Action Representation", area="Embodied AI", tags="VLA,Action Tokenization"),
                models.KnowledgeLink(title="Diffusion Policy", area="Robot Learning", tags="Manipulation,Imitation Learning"),
            ])
        db.commit()
    finally:
        db.close()


PROJECT_STATUSES = ["planning", "active", "blocked", "paused", "completed", "archived"]
PAPER_STATUSES = ["inbox", "to_read", "reading", "finished"]
EXPERIMENT_STATUSES = ["running", "pending", "completed", "failed"]
DASHBOARD_VENUES = ["ICRA", "IROS", "RA-L", "T-RO", "Science Robotics"]

DEFAULT_SETTINGS = {
    "general.language": "zh-CN",
    "paths.projects_root": "/home/robot",
    "paths.knowledge_root": "/home/robot/文档/Obsidian Vault",
    "paths.obsidian_vault": "/home/robot/文档/Obsidian Vault",
    "paths.dataset_root": "/home/robot/datasets",
    "paths.experiment_root": "/home/robot/experiments",
    "integrations.obsidian.enabled": "false",
    "integrations.obsidian.vault_path": "",
    "integrations.obsidian.knowledge_root": "Knowledge",
    "integrations.obsidian.use_obsidian_uri": "true",
    "integrations.zotero.enabled": "false",
    "integrations.zotero.connection_mode": "web_api",
    "integrations.zotero.user_id": "",
    "integrations.zotero.library": "My Library",
    "integrations.github.enabled": "false",
    "integrations.github.username": "",
    "integrations.github.default_owner": "",
    "integrations.github.default_branch": "main",
}

SECRET_KEYS = {
    "integrations.zotero.api_key",
    "integrations.github.personal_access_token",
}


def parse_bool(value: str) -> bool:
    return value.lower() in {"1", "true", "yes", "on"}


def bool_to_setting(value: bool) -> str:
    return "true" if value else "false"


def mask_secret(value: str | None) -> str | None:
    if not value:
        return None
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}{'*' * 6}{value[-4:]}"


def setting_value(db: Session, key: str) -> str:
    item = db.get(models.SystemSetting, key)
    return item.value if item else DEFAULT_SETTINGS.get(key, "")


def secret_value(db: Session, key: str) -> str:
    item = db.get(models.SecretSetting, key)
    return item.value if item else ""


def put_setting(db: Session, key: str, value: str) -> None:
    item = db.get(models.SystemSetting, key)
    if not item:
        item = models.SystemSetting(key=key, value=value)
        db.add(item)
    else:
        item.value = value


def put_secret(db: Session, key: str, value: str | None) -> None:
    if value is None or value == "":
        return
    item = db.get(models.SecretSetting, key)
    if not item:
        item = models.SecretSetting(key=key, value=value)
        db.add(item)
    else:
        item.value = value


def build_settings(db: Session) -> schemas.SystemSettingsOut:
    zotero_key = secret_value(db, "integrations.zotero.api_key")
    github_token = secret_value(db, "integrations.github.personal_access_token")
    return schemas.SystemSettingsOut(
        general=schemas.GeneralSettings(language=setting_value(db, "general.language")),
        paths=schemas.PathSettings(
            projects_root=setting_value(db, "paths.projects_root"),
            knowledge_root=setting_value(db, "paths.knowledge_root"),
            obsidian_vault=setting_value(db, "paths.obsidian_vault"),
            dataset_root=setting_value(db, "paths.dataset_root"),
            experiment_root=setting_value(db, "paths.experiment_root"),
        ),
        integrations=schemas.IntegrationSettings(
            obsidian=schemas.ObsidianSettings(
                enabled=parse_bool(setting_value(db, "integrations.obsidian.enabled")),
                vault_path=setting_value(db, "integrations.obsidian.vault_path"),
                knowledge_root=setting_value(db, "integrations.obsidian.knowledge_root"),
                use_obsidian_uri=parse_bool(setting_value(db, "integrations.obsidian.use_obsidian_uri")),
            ),
            zotero=schemas.ZoteroSettings(
                enabled=parse_bool(setting_value(db, "integrations.zotero.enabled")),
                connection_mode=setting_value(db, "integrations.zotero.connection_mode"),
                user_id=setting_value(db, "integrations.zotero.user_id"),
                api_key_masked=mask_secret(zotero_key),
                library=setting_value(db, "integrations.zotero.library"),
            ),
            github=schemas.GitHubSettings(
                enabled=parse_bool(setting_value(db, "integrations.github.enabled")),
                username=setting_value(db, "integrations.github.username"),
                personal_access_token_masked=mask_secret(github_token),
                default_owner=setting_value(db, "integrations.github.default_owner"),
                default_branch=setting_value(db, "integrations.github.default_branch"),
            ),
        ),
    )


def store_settings(db: Session, payload: schemas.SystemSettingsUpdate) -> schemas.SystemSettingsOut:
    if payload.general:
        put_setting(db, "general.language", payload.general.language)
    if payload.paths:
        for key, value in payload.paths.model_dump().items():
            put_setting(db, f"paths.{key}", str(value))
    if payload.integrations:
        obsidian = payload.integrations.obsidian
        put_setting(db, "integrations.obsidian.enabled", bool_to_setting(obsidian.enabled))
        put_setting(db, "integrations.obsidian.vault_path", obsidian.vault_path)
        put_setting(db, "integrations.obsidian.knowledge_root", obsidian.knowledge_root)
        put_setting(db, "integrations.obsidian.use_obsidian_uri", bool_to_setting(obsidian.use_obsidian_uri))

        zotero = payload.integrations.zotero
        put_setting(db, "integrations.zotero.enabled", bool_to_setting(zotero.enabled))
        put_setting(db, "integrations.zotero.connection_mode", zotero.connection_mode)
        put_setting(db, "integrations.zotero.user_id", zotero.user_id)
        put_setting(db, "integrations.zotero.library", zotero.library)
        put_secret(db, "integrations.zotero.api_key", zotero.api_key)

        github = payload.integrations.github
        put_setting(db, "integrations.github.enabled", bool_to_setting(github.enabled))
        put_setting(db, "integrations.github.username", github.username)
        put_setting(db, "integrations.github.default_owner", github.default_owner)
        put_setting(db, "integrations.github.default_branch", github.default_branch)
        put_secret(db, "integrations.github.personal_access_token", github.personal_access_token)
    db.commit()
    return build_settings(db)


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
        "task_id": session.task_id,
        "project_id": session.project_id,
        "note": session.note,
        "created_at": session.created_at.isoformat(),
        "updated_at": session.updated_at.isoformat(),
        "elapsed_seconds": focus_elapsed_seconds(session),
        "task_title": session.task.title if session.task else None,
        "project_name": session.project.name if session.project else None,
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
    text = f"{experiment.result or ''} {experiment.conclusion or ''}".lower()
    if any(word in text for word in ["fail", "failed", "error", "失败"]):
        return "failed"
    if experiment.conclusion:
        return "completed"
    if experiment.result:
        return "running"
    return "pending"


def milestone_summary(project: models.Project) -> tuple[str | None, str | None, float]:
    milestones = sorted(project.milestones, key=lambda item: (item.order_index, item.id))
    if not milestones:
        return None, None, project.progress
    weighted = sum(item.progress * item.weight for item in milestones)
    total_weight = sum(item.weight for item in milestones) or 1
    current_index = next((index for index, item in enumerate(milestones) if item.progress < 100), len(milestones) - 1)
    current = milestones[current_index].title if milestones else None
    next_item = next((item.title for item in milestones[current_index + 1:] if item.progress < 100), None)
    return current, next_item, round(weighted / total_weight, 1)


def git_summary_for_project(project: models.Project) -> dict[str, Any]:
    base = {
        "project_id": project.id,
        "project_name": project.name,
        "branch": project.branch,
        "modified_files": 0,
        "unpushed_commits": 0,
        "last_commit": None,
        "ok": False,
    }
    try:
        path = Path(project.path).expanduser()
        if not path.exists() or not (path / ".git").exists():
            return base
        status = git_service.status(str(path))
        unpushed = git_service.run_git(str(path), ["rev-list", "--count", "@{u}..HEAD"])
        base.update({
            "branch": status.get("branch") or project.branch,
            "modified_files": len(status.get("changes", [])),
            "unpushed_commits": int(unpushed["stdout"] or 0) if unpushed["ok"] else 0,
            "last_commit": (status.get("recent_commits") or [None])[0],
            "ok": status.get("is_repo", False),
        })
    except Exception as exc:
        base["error"] = str(exc)
    return base


def build_dashboard_summary(db: Session) -> dict[str, Any]:
    today = datetime.utcnow().strftime("%Y-%m-%d")
    settings = build_settings(db)
    today_tasks = db.query(models.Task).filter((models.Task.due_date == today) | (models.Task.due_date.is_(None))).order_by(models.Task.id.desc()).limit(12).all()
    completed_today = sum(1 for task in today_tasks if task.status == "done")

    projects = db.query(models.Project).order_by(models.Project.updated_at.desc()).all()
    project_counts = {status: 0 for status in PROJECT_STATUSES}
    featured_projects = []
    for project in projects:
        status = (project.status or "active").lower()
        if status in project_counts:
            project_counts[status] += 1
        current, next_item, progress = milestone_summary(project)
        featured_projects.append({
            "id": project.id,
            "name": project.name,
            "status": status,
            "progress": progress,
            "current_milestone": current,
            "next_milestone": next_item,
        })

    papers = db.query(models.Paper).order_by(models.Paper.updated_at.desc()).all()
    paper_status_counts = {status: 0 for status in PAPER_STATUSES}
    venue_counts = {venue: 0 for venue in DASHBOARD_VENUES}
    for paper in papers:
        status = (paper.status or "inbox").lower().replace(" ", "_").replace("-", "_")
        if status in {"to_read", "todo"}:
            status = "to_read"
        if status in {"done", "completed"}:
            status = "finished"
        if status in paper_status_counts:
            paper_status_counts[status] += 1
        if paper.venue in venue_counts:
            venue_counts[paper.venue] += 1
    currently_reading = [paper for paper in papers if (paper.status or "").lower() == "reading"][:5]
    recently_finished = [paper for paper in papers if (paper.status or "").lower() in {"finished", "done", "completed"}][:5]

    experiments = db.query(models.Experiment).order_by(models.Experiment.updated_at.desc()).all()
    experiment_counts = {status: 0 for status in EXPERIMENT_STATUSES}
    experiments_by_status = []
    for experiment in experiments:
        status = infer_experiment_status(experiment)
        experiment_counts[status] += 1
        experiments_by_status.append((experiment, status))
    running_experiments = [item for item, status in experiments_by_status if status == "running"][:5]
    recent_results = [item for item, status in experiments_by_status if status in {"completed", "failed"}][:5]

    knowledge_query = db.query(models.KnowledgeLink).order_by(models.KnowledgeLink.updated_at.desc())
    week_start = focus_range_start("week")
    git_projects = [git_summary_for_project(project) for project in projects[:8]]
    attention = []
    for project in projects:
        if (project.status or "").lower() == "blocked":
            attention.append({"kind": "project_blocked", "severity": "warning", "title": project.name, "message": "Project is blocked"})
        if datetime.utcnow() - project.updated_at > timedelta(days=7):
            attention.append({"kind": "project_stale", "severity": "info", "title": project.name, "message": "No project update for more than 7 days"})
    old_papers = [paper for paper in papers if (paper.status or "inbox").lower() in {"inbox", "to_read", "todo"} and datetime.utcnow() - paper.created_at > timedelta(days=14)]
    if old_papers:
        attention.append({"kind": "paper_waiting", "severity": "info", "title": "Literature", "message": f"{len(old_papers)} papers waiting more than 14 days"})
    no_conclusion = [experiment for experiment in experiments if not experiment.conclusion]
    if no_conclusion:
        attention.append({"kind": "experiment_no_conclusion", "severity": "info", "title": "Experiments", "message": f"{len(no_conclusion)} experiments have no conclusion"})
    for item in git_projects:
        if item.get("unpushed_commits", 0) > 0:
            attention.append({"kind": "git_unpushed", "severity": "warning", "title": item["project_name"], "message": f"{item['unpushed_commits']} local commits not pushed"})

    current_session = current_focus_session(db)
    return {
        "today": {
            "date": today,
            "tasks": [schemas.TaskOut.model_validate(task).model_dump(mode="json") for task in today_tasks],
            "completed_tasks": completed_today,
            "total_tasks": len(today_tasks),
            "completion_rate": round((completed_today / len(today_tasks)) * 100, 1) if today_tasks else 0,
            "courses": [],
            "schedule": [],
            "plan": [task.title for task in today_tasks if task.status != "done"][:5],
        },
        "projects": {
            "total": len(projects),
            "counts": project_counts,
            "featured": sorted(featured_projects, key=lambda item: (item["status"] != "active", -item["progress"]))[:6],
        },
        "papers": {
            "total": len(papers),
            "status_counts": paper_status_counts,
            "venue_counts": venue_counts,
            "currently_reading": [schemas.PaperOut.model_validate(paper).model_dump(mode="json") for paper in currently_reading],
            "recently_finished": [schemas.PaperOut.model_validate(paper).model_dump(mode="json") for paper in recently_finished],
        },
        "experiments": {
            "total": len(experiments),
            "counts": experiment_counts,
            "running": [schemas.ExperimentOut.model_validate(item).model_dump(mode="json") for item in running_experiments],
            "recent_results": [schemas.ExperimentOut.model_validate(item).model_dump(mode="json") for item in recent_results],
            "research_ideas_pending": db.query(models.ResearchIdea).filter(models.ResearchIdea.status == "candidate").count(),
            "research_ideas": [item.title for item in db.query(models.ResearchIdea).order_by(models.ResearchIdea.updated_at.desc()).limit(5).all()],
        },
        "knowledge": {
            "obsidian_connected": bool(settings.integrations.obsidian.enabled and settings.integrations.obsidian.vault_path and Path(settings.integrations.obsidian.vault_path).expanduser().exists()),
            "total_notes": db.query(models.KnowledgeLink).count(),
            "updated_this_week": db.query(models.KnowledgeLink).filter(models.KnowledgeLink.updated_at >= week_start).count(),
            "recently_updated": [schemas.KnowledgeLinkOut.model_validate(item).model_dump(mode="json") for item in knowledge_query.limit(5).all()],
        },
        "git": {"projects": git_projects},
        "focus": {
            "current_session": focus_out(current_session),
            "today_duration": focus_duration_for_range(db, "today"),
            "week_duration": focus_duration_for_range(db, "week"),
        },
        "attention": attention[:10],
    }


@app.get("/")
async def root() -> dict:
    return {"name": "RoboResearch Workbench Local API", "ok": True, "translation": translation_status()}


@app.get("/health")
async def health() -> dict:
    return {"ok": True, "translation": translation_status()}


@app.get("/summary")
def summary(db: Session = Depends(get_db)) -> dict:
    tasks_total = db.query(models.Task).count()
    tasks_done = db.query(models.Task).filter(models.Task.status == "done").count()
    paper_counts = db.query(models.Paper.venue, func.count(models.Paper.id)).group_by(models.Paper.venue).all()
    return {
        "projects": db.query(models.Project).count(),
        "active_projects": db.query(models.Project).filter(models.Project.status == "active").count(),
        "tasks_total": tasks_total,
        "tasks_done": tasks_done,
        "papers": db.query(models.Paper).count(),
        "reading_notes": db.query(models.ReadingNote).count(),
        "experiments": db.query(models.Experiment).count(),
        "knowledge_links": db.query(models.KnowledgeLink).count(),
        "papers_by_venue": {venue: count for venue, count in paper_counts},
    }


@app.get("/api/dashboard/summary", response_model=schemas.DashboardSummaryOut)
@app.get("/dashboard/summary", response_model=schemas.DashboardSummaryOut)
def dashboard_summary(db: Session = Depends(get_db)) -> dict:
    return build_dashboard_summary(db)


@app.get("/api/settings", response_model=schemas.SystemSettingsOut)
@app.get("/settings", response_model=schemas.SystemSettingsOut)
def get_settings(db: Session = Depends(get_db)) -> schemas.SystemSettingsOut:
    return build_settings(db)


@app.patch("/api/settings", response_model=schemas.SystemSettingsOut)
@app.patch("/settings", response_model=schemas.SystemSettingsOut)
def update_settings(payload: schemas.SystemSettingsUpdate, db: Session = Depends(get_db)) -> schemas.SystemSettingsOut:
    return store_settings(db, payload)


@app.post("/api/settings/test/{integration}", response_model=schemas.SettingsTestResult)
@app.post("/settings/test/{integration}", response_model=schemas.SettingsTestResult)
def test_integration(integration: str, db: Session = Depends(get_db)) -> schemas.SettingsTestResult:
    settings = build_settings(db)
    if integration == "obsidian":
        vault = settings.integrations.obsidian.vault_path or settings.paths.obsidian_vault
        ok = bool(vault and Path(vault).expanduser().exists())
        return schemas.SettingsTestResult(ok=ok, message="Obsidian vault path is available." if ok else "Obsidian vault path does not exist.")
    if integration == "zotero":
        has_key = bool(secret_value(db, "integrations.zotero.api_key"))
        has_user = bool(settings.integrations.zotero.user_id)
        ok = not settings.integrations.zotero.enabled or settings.integrations.zotero.connection_mode == "local" or (has_key and has_user)
        return schemas.SettingsTestResult(ok=ok, message="Zotero settings are ready." if ok else "Zotero Web API requires both user ID and API key.")
    if integration == "github":
        has_token = bool(secret_value(db, "integrations.github.personal_access_token"))
        has_owner = bool(settings.integrations.github.default_owner or settings.integrations.github.username)
        ok = not settings.integrations.github.enabled or (has_token and has_owner)
        return schemas.SettingsTestResult(ok=ok, message="GitHub settings are ready." if ok else "GitHub integration requires a token and owner/username.")
    if integration == "paths":
        paths = settings.paths.model_dump()
        missing = [key for key, value in paths.items() if value and not Path(value).expanduser().exists()]
        ok = not missing
        return schemas.SettingsTestResult(ok=ok, message="All configured paths exist." if ok else f"Missing paths: {', '.join(missing)}")
    raise HTTPException(status_code=404, detail="Unknown integration")


@app.get("/api/focus/current")
@app.get("/focus/current")
def get_current_focus(db: Session = Depends(get_db)) -> dict:
    return {"current_session": focus_out(current_focus_session(db))}


@app.post("/api/focus/start")
@app.post("/focus/start")
def start_focus(payload: schemas.FocusSessionCreate, db: Session = Depends(get_db)) -> dict:
    if current_focus_session(db):
        raise HTTPException(status_code=409, detail="A focus session is already running or paused")
    if payload.task_id is not None:
        crud.get_item(db, models.Task, payload.task_id)
    if payload.project_id is not None:
        crud.get_item(db, models.Project, payload.project_id)
    session = models.FocusSession(
        task_id=payload.task_id,
        project_id=payload.project_id,
        note=payload.note,
        status="RUNNING",
        started_at=datetime.utcnow(),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return focus_out(session)


@app.post("/api/focus/{session_id}/pause")
@app.post("/focus/{session_id}/pause")
def pause_focus(session_id: int, db: Session = Depends(get_db)) -> dict:
    session = crud.get_item(db, models.FocusSession, session_id)
    if session.status != "RUNNING":
        raise HTTPException(status_code=400, detail="Only a running focus session can be paused")
    session.status = "PAUSED"
    session.paused_started_at = datetime.utcnow()
    db.commit()
    db.refresh(session)
    return focus_out(session)


@app.post("/api/focus/{session_id}/resume")
@app.post("/focus/{session_id}/resume")
def resume_focus(session_id: int, db: Session = Depends(get_db)) -> dict:
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


@app.post("/api/focus/{session_id}/finish")
@app.post("/focus/{session_id}/finish")
def finish_focus(session_id: int, db: Session = Depends(get_db)) -> dict:
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


@app.get("/api/focus/stats", response_model=schemas.FocusStatsOut)
@app.get("/focus/stats", response_model=schemas.FocusStatsOut)
def focus_stats(range: str = "today", db: Session = Depends(get_db)) -> schemas.FocusStatsOut:
    if range not in {"today", "week", "month"}:
        raise HTTPException(status_code=400, detail="Unsupported range")
    return schemas.FocusStatsOut(range=range, duration_seconds=focus_duration_for_range(db, range))


def default_layout() -> list[dict]:
    return [
        {"i": "today", "x": 0, "y": 0, "w": 4, "h": 4},
        {"i": "projects", "x": 4, "y": 0, "w": 4, "h": 4},
        {"i": "papers", "x": 8, "y": 0, "w": 4, "h": 4},
        {"i": "experiments", "x": 0, "y": 4, "w": 4, "h": 4},
        {"i": "capture", "x": 4, "y": 4, "w": 4, "h": 4},
        {"i": "knowledge", "x": 8, "y": 4, "w": 4, "h": 4},
    ]


@app.get("/dashboard/layout", response_model=schemas.DashboardLayoutOut)
def get_dashboard_layout(db: Session = Depends(get_db)) -> dict:
    item = db.get(models.DashboardLayout, "default")
    return {"layout": json.loads(item.layout_json) if item else default_layout()}


@app.put("/dashboard/layout", response_model=schemas.DashboardLayoutOut)
def put_dashboard_layout(payload: schemas.DashboardLayoutIn, db: Session = Depends(get_db)) -> dict:
    item = db.get(models.DashboardLayout, "default")
    if not item:
        item = models.DashboardLayout(id="default")
        db.add(item)
    item.layout_json = json.dumps(payload.layout)
    db.commit()
    return {"layout": payload.layout}


@app.get("/projects/discover")
def discover_projects() -> list[dict]:
    discovered = []
    for path in sorted(Path("/home/robot").iterdir()):
        if path.is_dir() and not path.name.startswith(".") and (path / ".git").exists():
            discovered.append({"name": path.name, "path": str(path), **git_service.status(str(path))})
    return discovered


@app.get("/projects", response_model=list[schemas.ProjectOut])
def list_projects(db: Session = Depends(get_db)):
    return crud.list_items(db, models.Project)


@app.post("/projects", response_model=schemas.ProjectOut)
def create_project(payload: schemas.ProjectCreate, db: Session = Depends(get_db)):
    path = Path(payload.path).expanduser()
    if not path.exists():
        raise HTTPException(status_code=400, detail="Project path does not exist")
    return crud.create_item(db, models.Project, payload)


@app.patch("/projects/{project_id}", response_model=schemas.ProjectOut)
def update_project(project_id: int, payload: schemas.ProjectUpdate, db: Session = Depends(get_db)):
    return crud.update_item(db, models.Project, project_id, payload)


@app.delete("/projects/{project_id}")
def delete_project(project_id: int, db: Session = Depends(get_db)):
    return crud.delete_item(db, models.Project, project_id)


@app.get("/projects/{project_id}/git/status")
def project_git_status(project_id: int, db: Session = Depends(get_db)) -> dict:
    project = crud.get_item(db, models.Project, project_id)
    try:
        return git_service.status(project.path)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/projects/{project_id}/git/diff")
def project_git_diff(project_id: int, file: str | None = None, db: Session = Depends(get_db)) -> dict:
    project = crud.get_item(db, models.Project, project_id)
    return git_service.diff(project.path, file)


@app.post("/projects/{project_id}/git/commit")
def project_git_commit(project_id: int, payload: schemas.GitCommitRequest, db: Session = Depends(get_db)) -> dict:
    project = crud.get_item(db, models.Project, project_id)
    return git_service.commit(project.path, payload.files, payload.message)


@app.post("/projects/{project_id}/git/push")
def project_git_push(project_id: int, payload: schemas.GitPushRequest, db: Session = Depends(get_db)) -> dict:
    project = crud.get_item(db, models.Project, project_id)
    return git_service.push(project.path, payload.remote, payload.branch, payload.confirm)


@app.get("/tasks", response_model=list[schemas.TaskOut])
def list_tasks(db: Session = Depends(get_db)):
    return crud.list_items(db, models.Task)


@app.post("/tasks", response_model=schemas.TaskOut)
def create_task(payload: schemas.TaskCreate, db: Session = Depends(get_db)):
    return crud.create_item(db, models.Task, payload)


@app.patch("/tasks/{task_id}", response_model=schemas.TaskOut)
def update_task(task_id: int, payload: schemas.TaskUpdate, db: Session = Depends(get_db)):
    return crud.update_item(db, models.Task, task_id, payload)


@app.delete("/tasks/{task_id}")
def delete_task(task_id: int, db: Session = Depends(get_db)):
    return crud.delete_item(db, models.Task, task_id)


@app.get("/project-progress", response_model=list[schemas.ProjectProgressLogOut])
def list_project_progress(date: str | None = None, project_id: int | None = None, db: Session = Depends(get_db)):
    query = db.query(models.ProjectProgressLog)
    if date:
        query = query.filter(models.ProjectProgressLog.date == date)
    if project_id:
        query = query.filter(models.ProjectProgressLog.project_id == project_id)
    return query.order_by(models.ProjectProgressLog.date.desc(), models.ProjectProgressLog.id.desc()).limit(300).all()


@app.post("/project-progress", response_model=schemas.ProjectProgressLogOut)
def create_project_progress(payload: schemas.ProjectProgressLogCreate, db: Session = Depends(get_db)):
    crud.get_item(db, models.Project, payload.project_id)
    return crud.create_item(db, models.ProjectProgressLog, payload)


@app.patch("/project-progress/{log_id}", response_model=schemas.ProjectProgressLogOut)
def update_project_progress(log_id: int, payload: schemas.ProjectProgressLogUpdate, db: Session = Depends(get_db)):
    if payload.project_id is not None:
        crud.get_item(db, models.Project, payload.project_id)
    return crud.update_item(db, models.ProjectProgressLog, log_id, payload)


@app.delete("/project-progress/{log_id}")
def delete_project_progress(log_id: int, db: Session = Depends(get_db)):
    return crud.delete_item(db, models.ProjectProgressLog, log_id)


@app.post("/papers/search", response_model=SearchResponse)
async def search_papers(request: SearchRequest) -> SearchResponse:
    openalex_papers = await search_openalex(request)
    crossref_papers = await search_crossref(request)
    papers_by_key = {}
    for paper in [*crossref_papers, *openalex_papers]:
        key = (paper.doi or paper.id).lower()
        current = papers_by_key.get(key)
        if current is None or paper.relevance >= current.relevance:
            papers_by_key[key] = paper
    papers = sorted(papers_by_key.values(), key=lambda paper: (paper.relevance, paper.year or 0), reverse=True)
    return SearchResponse(papers=await translate_papers(papers))


@app.post("/papers/import-zotero")
async def papers_import_zotero(request: ZoteroImportRequest) -> dict:
    try:
        return await import_to_zotero(request)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/papers/attach-pdf")
async def papers_attach_pdf(request: ZoteroAttachPdfRequest) -> dict:
    try:
        return await attach_pdf_to_zotero(request)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/zotero/status")
async def get_zotero_status() -> dict:
    return await zotero_status()


@app.get("/papers", response_model=list[schemas.PaperOut])
def list_papers(venue: str | None = None, db: Session = Depends(get_db)):
    query = db.query(models.Paper)
    if venue:
        query = query.filter(models.Paper.venue == venue)
    return query.order_by(models.Paper.id.desc()).limit(300).all()


@app.post("/papers", response_model=schemas.PaperOut)
def create_paper(payload: schemas.PaperCreate, db: Session = Depends(get_db)):
    return crud.create_item(db, models.Paper, payload)


@app.patch("/papers/{paper_id}", response_model=schemas.PaperOut)
def update_paper(paper_id: int, payload: schemas.PaperUpdate, db: Session = Depends(get_db)):
    return crud.update_item(db, models.Paper, paper_id, payload)


@app.delete("/papers/{paper_id}")
def delete_paper(paper_id: int, db: Session = Depends(get_db)):
    return crud.delete_item(db, models.Paper, paper_id)


@app.get("/reading-notes", response_model=list[schemas.ReadingNoteOut])
def list_reading_notes(db: Session = Depends(get_db)):
    return crud.list_items(db, models.ReadingNote)


@app.post("/reading-notes", response_model=schemas.ReadingNoteOut)
def create_reading_note(payload: schemas.ReadingNoteCreate, db: Session = Depends(get_db)):
    return crud.create_item(db, models.ReadingNote, payload)


@app.patch("/reading-notes/{note_id}", response_model=schemas.ReadingNoteOut)
def update_reading_note(note_id: int, payload: schemas.ReadingNoteUpdate, db: Session = Depends(get_db)):
    return crud.update_item(db, models.ReadingNote, note_id, payload)


@app.delete("/reading-notes/{note_id}")
def delete_reading_note(note_id: int, db: Session = Depends(get_db)):
    return crud.delete_item(db, models.ReadingNote, note_id)


@app.get("/experiments", response_model=list[schemas.ExperimentOut])
def list_experiments(db: Session = Depends(get_db)):
    return crud.list_items(db, models.Experiment)


@app.post("/experiments", response_model=schemas.ExperimentOut)
def create_experiment(payload: schemas.ExperimentCreate, db: Session = Depends(get_db)):
    return crud.create_item(db, models.Experiment, payload)


@app.patch("/experiments/{experiment_id}", response_model=schemas.ExperimentOut)
def update_experiment(experiment_id: int, payload: schemas.ExperimentUpdate, db: Session = Depends(get_db)):
    return crud.update_item(db, models.Experiment, experiment_id, payload)


@app.delete("/experiments/{experiment_id}")
def delete_experiment(experiment_id: int, db: Session = Depends(get_db)):
    return crud.delete_item(db, models.Experiment, experiment_id)


@app.get("/knowledge-links", response_model=list[schemas.KnowledgeLinkOut])
def list_knowledge_links(db: Session = Depends(get_db)):
    return crud.list_items(db, models.KnowledgeLink)


@app.post("/knowledge-links", response_model=schemas.KnowledgeLinkOut)
def create_knowledge_link(payload: schemas.KnowledgeLinkCreate, db: Session = Depends(get_db)):
    return crud.create_item(db, models.KnowledgeLink, payload)


@app.patch("/knowledge-links/{knowledge_id}", response_model=schemas.KnowledgeLinkOut)
def update_knowledge_link(knowledge_id: int, payload: schemas.KnowledgeLinkUpdate, db: Session = Depends(get_db)):
    return crud.update_item(db, models.KnowledgeLink, knowledge_id, payload)


@app.delete("/knowledge-links/{knowledge_id}")
def delete_knowledge_link(knowledge_id: int, db: Session = Depends(get_db)):
    return crud.delete_item(db, models.KnowledgeLink, knowledge_id)
