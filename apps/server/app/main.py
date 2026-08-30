from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, inspect, or_, text
from sqlalchemy.orm import Session

from . import crud, git_service, github_service, models, project_progress_service, project_scanner_service, schemas, settings_service
from .database import Base, engine, get_db
from .paper_integrations.crossref import search_crossref
from .paper_integrations.models import Paper as SearchPaperModel, SearchRequest, SearchResponse, ZoteroAttachPdfRequest, ZoteroImportRequest
from .paper_integrations.openalex import search_openalex
from .paper_integrations.translator import translate_papers, translation_status
from .paper_integrations.zotero import attach_pdf_to_zotero, get_zotero_item_sync_state, import_to_zotero, zotero_status

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
    migrate_schema()
    seed_defaults()


def migrate_schema() -> None:
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    with engine.begin() as conn:
        if "projects" in existing_tables:
            columns = {column["name"] for column in inspector.get_columns("projects")}
            additions = {
                "progress_mode": "VARCHAR(40) DEFAULT 'AUTO'",
                "project_type": "VARCHAR(120)",
                "tags": "TEXT",
                "current_stage": "VARCHAR(240)",
                "next_stage": "VARCHAR(240)",
                "health": "VARCHAR(40)",
                "default_branch": "VARCHAR(200)",
                "experiment_dir": "VARCHAR(800)",
                "results_dir": "VARCHAR(800)",
                "links": "TEXT",
            }
            for name, ddl in additions.items():
                if name not in columns:
                    conn.execute(text(f"ALTER TABLE projects ADD COLUMN {name} {ddl}"))
        if "milestones" in existing_tables:
            columns = {column["name"] for column in inspector.get_columns("milestones")}
            if "stage_id" not in columns:
                conn.execute(text("ALTER TABLE milestones ADD COLUMN stage_id INTEGER"))
            if "status" not in columns:
                conn.execute(text("ALTER TABLE milestones ADD COLUMN status VARCHAR(40) DEFAULT 'pending'"))
        if "tasks" in existing_tables:
            columns = {column["name"] for column in inspector.get_columns("tasks")}
            if "milestone_id" not in columns:
                conn.execute(text("ALTER TABLE tasks ADD COLUMN milestone_id INTEGER"))
        if "experiments" in existing_tables:
            columns = {column["name"] for column in inspector.get_columns("experiments")}
            if "git_branch" not in columns:
                conn.execute(text("ALTER TABLE experiments ADD COLUMN git_branch VARCHAR(200)"))
        if "papers" in existing_tables:
            columns = {column["name"] for column in inspector.get_columns("papers")}
            additions = {
                "reading_mode": "VARCHAR(40)",
                "reading_purpose": "VARCHAR(80)",
                "queued_at": "DATETIME",
                "source_url": "VARCHAR(1000)",
                "zotero_item_key": "VARCHAR(80)",
                "zotero_attachment_key": "VARCHAR(80)",
                "zotero_library": "VARCHAR(120)",
                "zotero_pdf_attached": "BOOLEAN DEFAULT 0",
                "zotero_pdf_status": "VARCHAR(80)",
                "pdf_status": "VARCHAR(80) DEFAULT 'NONE'",
                "pdf_source": "VARCHAR(80)",
                "pdf_last_checked_at": "DATETIME",
                "pdf_error_code": "VARCHAR(120)",
                "pdf_error_message": "VARCHAR(500)",
                "zotero_synced_at": "DATETIME",
            }
            for name, ddl in additions.items():
                if name not in columns:
                    conn.execute(text(f"ALTER TABLE papers ADD COLUMN {name} {ddl}"))
            if "source_url" not in columns and "url" in columns:
                conn.execute(text("UPDATE papers SET source_url = url WHERE source_url IS NULL"))
            if "pdf_status" not in columns:
                conn.execute(text("UPDATE papers SET pdf_status = CASE WHEN COALESCE(zotero_pdf_attached, 0) = 1 THEN 'ATTACHED' ELSE 'NONE' END"))
        if "reading_notes" in existing_tables:
            columns = {column["name"] for column in inspector.get_columns("reading_notes")}
            additions = {
                "content_markdown": "TEXT DEFAULT ''",
                "reading_status_snapshot": "VARCHAR(40)",
                "reading_mode": "VARCHAR(40)",
                "one_sentence_summary": "TEXT",
                "relevance_to_me": "TEXT",
                "related_project_id": "INTEGER",
            }
            for name, ddl in additions.items():
                if name not in columns:
                    conn.execute(text(f"ALTER TABLE reading_notes ADD COLUMN {name} {ddl}"))
            if "content_markdown" not in columns:
                conn.execute(text("UPDATE reading_notes SET content_markdown = COALESCE(content, '')"))
        if "research_ideas" in existing_tables:
            columns = {column["name"] for column in inspector.get_columns("research_ideas")}
            additions = {
                "source_paper_id": "INTEGER",
                "source_reading_note_id": "INTEGER",
                "related_project_id": "INTEGER",
            }
            for name, ddl in additions.items():
                if name not in columns:
                    conn.execute(text(f"ALTER TABLE research_ideas ADD COLUMN {name} {ddl}"))
        if "focus_sessions" in existing_tables:
            columns = {column["name"] for column in inspector.get_columns("focus_sessions")}
            additions = {
                "focus_type": "VARCHAR(80)",
                "context_type": "VARCHAR(80)",
                "paper_id": "INTEGER",
                "reading_note_id": "INTEGER",
            }
            for name, ddl in additions.items():
                if name not in columns:
                    conn.execute(text(f"ALTER TABLE focus_sessions ADD COLUMN {name} {ddl}"))


def seed_defaults() -> None:
    db = next(get_db())
    try:
        if db.query(models.Project).count() == 0:
            for name in ["IsaacLab", "LLM-as-BT-Planner", "Hrs_loco_manipulation", "DRL_robot_navigation_ros2"]:
                path = Path("/home/robot") / name
                if path.exists():
                    scan = project_scanner_service.scan_project(str(path))
                    project = models.Project(
                        name=name,
                        path=str(path),
                        description="Imported from /home/robot for local research management.",
                        status="Active",
                        progress=0,
                        progress_mode="AUTO",
                        project_type=scan.get("project_type"),
                        tags=", ".join(scan.get("tags", [])),
                        remote_url=scan.get("remote_url"),
                        branch=scan.get("branch"),
                    )
                    db.add(project)
                    db.flush()
                    create_default_stages(db, project.id, scan.get("suggested_stages", []))
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


def normalize_project_status(value: str | None) -> str:
    if not value:
        return "Active"
    mapping = {item.lower(): item for item in schemas.PROJECT_STATUSES}
    return mapping.get(value.lower(), value)


def normalize_paper_status(value: str | None) -> str:
    if not value:
        return "Inbox"
    aliases = {"inbox": "Inbox", "candidate": "Candidate", "to_read": "To Read", "to read": "To Read", "skimming": "Skimming", "reading": "Reading", "deep_reading": "Deep Reading", "deep reading": "Deep Reading", "finished": "Finished", "reference": "Reference", "dropped": "Dropped"}
    return aliases.get(value.strip().lower(), value)


def normalize_reading_mode(value: str | None) -> str | None:
    if not value:
        return None
    upper = value.strip().upper().replace(" ", "_")
    mapping = {"SCANNING": "SCAN", "SKIMMING": "SKIM", "READING": "READ", "DEEP_READING": "DEEP"}
    return mapping.get(upper, upper if upper in schemas.READING_MODES else value)


def reading_note_template(paper: models.Paper | None = None) -> str:
    title = paper.title if paper else "Untitled Paper"
    return f"""# Reading Note: {title}

## 1. Why did I read this?

## 2. One Sentence Summary

## 3. Problem

## 4. Core Idea

## 5. Architecture

## 6. Key Technical Details

## 7. Experiments

## 8. What is actually useful to me?

## 9. Limitations

## 10. Questions

## 11. Ideas

## 12. Knowledge to Extract
"""


def normalize_doi(doi: str | None) -> str | None:
    if not doi:
        return None
    return doi.strip().lower().removeprefix("https://doi.org/").removeprefix("http://doi.org/").removeprefix("doi:").strip() or None


def title_year_key(title: str | None, year: int | None) -> str | None:
    if not title:
        return None
    normalized_title = re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", title.lower())).strip()
    return f"{normalized_title}|{year or ''}" if normalized_title else None


def find_existing_paper(db: Session, title: str, year: int | None, doi: str | None) -> models.Paper | None:
    normalized = normalize_doi(doi)
    if normalized:
        existing = db.query(models.Paper).filter(func.lower(models.Paper.doi) == normalized).first()
        if existing:
            return existing
    key = title_year_key(title, year)
    if not key:
        return None
    for paper in db.query(models.Paper).filter(models.Paper.year == year).all():
        if title_year_key(paper.title, paper.year) == key:
            return paper
    return None


def normalize_venue(value: str | None) -> str:
    if not value:
        return "Others"
    lower = value.lower()
    if "icra" in lower:
        return "ICRA"
    if "iros" in lower:
        return "IROS"
    if "robotics and automation letters" in lower or "ra-l" in lower or "ral" == lower.strip():
        return "RA-L"
    if "transactions on robotics" in lower or "t-ro" in lower or "tro" == lower.strip():
        return "T-RO"
    if "science robotics" in lower:
        return "Science Robotics"
    return value if value in {"ICRA", "IROS", "RA-L", "T-RO", "Science Robotics"} else "Others"


def search_paper_to_db_payload(paper: SearchPaperModel | dict[str, Any], status: str = "Candidate") -> dict[str, Any]:
    model = paper if isinstance(paper, SearchPaperModel) else SearchPaperModel.model_validate(paper)
    return {
        "title": model.title,
        "translated_title": model.translated_title,
        "abstract": model.abstract,
        "translated_abstract": model.translated_abstract,
        "authors": ", ".join(model.authors),
        "year": model.year,
        "venue": normalize_venue(model.source_label or model.venue),
        "tags": ", ".join(model.matched_keywords),
        "doi": normalize_doi(model.doi),
        "url": model.url,
        "source_url": model.url,
        "pdf_url": model.pdf_url,
        "status": status,
    }


def merge_search_papers(current: SearchPaperModel, incoming: SearchPaperModel) -> SearchPaperModel:
    winner = incoming if incoming.relevance > current.relevance else current
    other = current if winner is incoming else incoming
    updates: dict[str, Any] = {}
    for field in ("pdf_url", "url", "abstract", "translated_abstract", "translated_title", "doi", "venue", "source_label"):
        if not getattr(winner, field) and getattr(other, field):
            updates[field] = getattr(other, field)
    if not winner.is_oa and other.is_oa:
        updates["is_oa"] = True
    keywords = list(dict.fromkeys([*(winner.matched_keywords or []), *(other.matched_keywords or [])]))
    if keywords != winner.matched_keywords:
        updates["matched_keywords"] = keywords
    return winner.model_copy(update=updates) if updates else winner


def db_paper_to_search_model(paper: models.Paper) -> SearchPaperModel:
    tags = [tag.strip() for tag in (paper.tags or "").split(",") if tag.strip()]
    authors = [author.strip() for author in (paper.authors or "").split(",") if author.strip()]
    return SearchPaperModel(
        id=paper.doi or paper.url or f"workbench:{paper.id}",
        title=paper.title,
        translated_title=paper.translated_title,
        abstract=paper.abstract,
        translated_abstract=paper.translated_abstract,
        authors=authors,
        year=paper.year,
        venue=paper.venue,
        source_id=paper.venue,
        source_label=paper.venue,
        doi=paper.doi,
        url=paper.url,
        pdf_url=paper.pdf_url,
        is_oa=bool(paper.pdf_url),
        matched_keywords=tags,
    )


def apply_pdf_state(
    paper: models.Paper,
    *,
    status: str,
    source: str | None = None,
    attachment_key: str | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
) -> None:
    paper.pdf_status = status
    paper.zotero_pdf_status = status
    paper.zotero_pdf_attached = status == "ATTACHED"
    if source is not None:
        paper.pdf_source = source
    if attachment_key:
        paper.zotero_attachment_key = attachment_key
    paper.pdf_error_code = error_code
    paper.pdf_error_message = (error_message or "")[:500] or None
    paper.pdf_last_checked_at = datetime.utcnow()
    paper.zotero_synced_at = datetime.utcnow()


def apply_zotero_sync_state_to_paper(paper: models.Paper, state: dict[str, Any]) -> None:
    attachment_key = state.get("zotero_attachment_key")
    if state.get("pdf_status") == "ATTACHED" or attachment_key:
        apply_pdf_state(
            paper,
            status="ATTACHED",
            source=state.get("pdf_source") or "ZOTERO",
            attachment_key=attachment_key,
        )
    else:
        apply_pdf_state(
            paper,
            status="NONE",
            source=state.get("pdf_source"),
            error_code="PDF_NOT_FOUND",
            error_message="No PDF child attachment was found in Zotero.",
        )


def upsert_paper(db: Session, data: dict[str, Any]) -> models.Paper:
    existing = find_existing_paper(db, data["title"], data.get("year"), data.get("doi"))
    if existing:
        for key, value in data.items():
            if value is not None and (key != "status" or existing.status in {"inbox", "Inbox", "Candidate"}):
                setattr(existing, key, value)
        db.commit()
        db.refresh(existing)
        return existing
    item = models.Paper(**data)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def zotero_item_result(zotero_result: dict, index: int = 0) -> dict[str, Any]:
    for item in zotero_result.get("item_results") or []:
        if item.get("index") == index:
            return item
    item_keys = zotero_result.get("item_keys") or []
    item_key = item_keys[index] if len(item_keys) > index else None
    return {"item_key": item_key, "pdf_attached": False, "pdf_status": "unknown"}


def apply_zotero_import_result_to_payload(db: Session, data: dict[str, Any], zotero_result: dict, index: int = 0) -> None:
    item = zotero_item_result(zotero_result, index)
    item_key = item.get("item_key")
    if item_key:
        data["zotero_item_key"] = item_key
        data["zotero_key"] = item_key
    data["zotero_library"] = setting_value(db, "integrations.zotero.library") or "My Library"
    pdf_status = item.get("pdf_status") or ("ATTACHED" if item.get("pdf_attached") else "NONE")
    data["zotero_attachment_key"] = item.get("zotero_attachment_key")
    data["zotero_pdf_attached"] = pdf_status == "ATTACHED"
    data["zotero_pdf_status"] = pdf_status
    data["pdf_status"] = pdf_status
    data["pdf_source"] = item.get("pdf_source")
    data["pdf_last_checked_at"] = datetime.utcnow()
    data["pdf_error_code"] = item.get("pdf_error_code")
    data["pdf_error_message"] = item.get("pdf_error_message")
    data["zotero_synced_at"] = datetime.utcnow()


def apply_zotero_import_result_to_paper(db: Session, paper: models.Paper, zotero_result: dict, index: int = 0) -> None:
    data: dict[str, Any] = {}
    apply_zotero_import_result_to_payload(db, data, zotero_result, index)
    for key, value in data.items():
        setattr(paper, key, value)


def safe_markdown_filename(title: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", title).strip("-._").lower()[:100]
    return f"{slug or 'reading-note'}.md"


def note_content(note: models.ReadingNote) -> str:
    return note.content_markdown or note.content or ""


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
    status_counts = {status: db.query(models.Project).filter(func.lower(models.Project.status) == status.lower()).count() for status in schemas.PROJECT_STATUSES}
    return {
        "projects": db.query(models.Project).count(),
        "active_projects": status_counts.get("Active", 0),
        "projects_by_status": status_counts,
        "tasks_total": tasks_total,
        "tasks_done": tasks_done,
        "papers": db.query(models.Paper).count(),
        "reading_notes": db.query(models.ReadingNote).count(),
        "experiments": db.query(models.Experiment).count(),
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


@app.get("/settings", response_model=schemas.SystemSettingsOut)
def get_settings(db: Session = Depends(get_db)) -> dict:
    return {"settings": settings_service.get_settings(db)}


@app.put("/settings", response_model=schemas.SystemSettingsOut)
def put_settings(payload: schemas.SystemSettingsIn, db: Session = Depends(get_db)) -> dict:
    return {"settings": settings_service.update_settings(db, payload.settings)}


@app.get("/filesystem/directories")
def list_directories(path: str | None = Query(default=None)) -> dict:
    try:
        return project_scanner_service.list_directories(path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/projects/discover")
def discover_projects() -> list[dict]:
    discovered = []
    for path in sorted(Path("/home/robot").iterdir()):
        if path.is_dir() and not path.name.startswith(".") and (path / ".git").exists():
            discovered.append({"name": path.name, "path": str(path), **git_service.status(str(path))})
    return discovered


@app.get("/projects", response_model=list[schemas.ProjectOut])
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
        public_project(project)
    db.commit()
    return projects


@app.post("/projects/scan")
def scan_project(payload: schemas.ProjectScanRequest) -> dict:
    try:
        return project_scanner_service.scan_project(payload.path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/projects/register", response_model=schemas.ProjectOut)
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


@app.post("/projects", response_model=schemas.ProjectOut)
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


@app.patch("/projects/{project_id}", response_model=schemas.ProjectOut)
def update_project(project_id: int, payload: schemas.ProjectUpdate, db: Session = Depends(get_db)):
    if payload.status:
        payload.status = normalize_project_status(payload.status)
    project = crud.update_item(db, models.Project, project_id, payload)
    ensure_project_stages(db, project)
    project_progress_service.sync_project_progress(db, project)
    return public_project(project)


@app.delete("/projects/{project_id}")
def delete_project(project_id: int, db: Session = Depends(get_db)):
    return crud.delete_item(db, models.Project, project_id)


@app.get("/projects/{project_id}/detail")
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


@app.get("/projects/{project_id}/progress")
def get_project_progress(project_id: int, db: Session = Depends(get_db)) -> dict:
    project = project_or_404(db, project_id)
    ensure_project_stages(db, project)
    project_progress_service.sync_project_progress(db, project)
    return project_progress_service.project_progress(db, project)


@app.post("/projects/{project_id}/progress/initialize")
def initialize_project_progress(project_id: int, db: Session = Depends(get_db)) -> dict:
    project = project_or_404(db, project_id)
    ensure_project_stages(db, project)
    project_progress_service.sync_project_progress(db, project)
    project = public_project(project)
    return {
        "project": schemas.ProjectOut.model_validate(project).model_dump(mode="json"),
        "progress": project_progress_service.project_progress(db, project),
    }


@app.post("/project-stages", response_model=schemas.ProjectStageOut)
def create_stage(payload: schemas.ProjectStageCreate, db: Session = Depends(get_db)):
    stage = crud.create_item(db, models.ProjectStage, payload)
    project_progress_service.sync_project_progress(db, project_or_404(db, stage.project_id))
    return stage


@app.patch("/project-stages/{stage_id}", response_model=schemas.ProjectStageOut)
def update_stage(stage_id: int, payload: schemas.ProjectStageUpdate, db: Session = Depends(get_db)):
    stage = crud.update_item(db, models.ProjectStage, stage_id, payload)
    project_progress_service.sync_project_progress(db, project_or_404(db, stage.project_id))
    return stage


@app.post("/milestones", response_model=schemas.MilestoneOut)
def create_milestone(payload: schemas.MilestoneCreate, db: Session = Depends(get_db)):
    milestone = crud.create_item(db, models.Milestone, payload)
    project_progress_service.sync_project_progress(db, project_or_404(db, milestone.project_id))
    return milestone


@app.patch("/milestones/{milestone_id}", response_model=schemas.MilestoneOut)
def update_milestone(milestone_id: int, payload: schemas.MilestoneUpdate, db: Session = Depends(get_db)):
    milestone = crud.update_item(db, models.Milestone, milestone_id, payload)
    project_progress_service.sync_project_progress(db, project_or_404(db, milestone.project_id))
    return milestone


@app.post("/projects/{project_id}/git/init")
def project_git_init(project_id: int, db: Session = Depends(get_db)) -> dict:
    project = project_or_404(db, project_id)
    result = git_service.init_repo(project.path, project.default_branch or "main")
    return result


@app.get("/projects/{project_id}/git/status")
def project_git_status(project_id: int, db: Session = Depends(get_db)) -> dict:
    project = project_or_404(db, project_id)
    try:
        return git_service.status(project.path)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/projects/{project_id}/git/diff")
def project_git_diff(project_id: int, file: str | None = None, staged: bool = False, db: Session = Depends(get_db)) -> dict:
    project = project_or_404(db, project_id)
    return git_service.diff(project.path, file, staged)


@app.post("/projects/{project_id}/git/stage")
def project_git_stage(project_id: int, payload: schemas.GitStageRequest, db: Session = Depends(get_db)) -> dict:
    project = project_or_404(db, project_id)
    return git_service.stage(project.path, payload.files)


@app.post("/projects/{project_id}/git/unstage")
def project_git_unstage(project_id: int, payload: schemas.GitStageRequest, db: Session = Depends(get_db)) -> dict:
    project = project_or_404(db, project_id)
    return git_service.unstage(project.path, payload.files)


@app.post("/projects/{project_id}/git/commit")
def project_git_commit(project_id: int, payload: schemas.GitCommitRequest, db: Session = Depends(get_db)) -> dict:
    project = project_or_404(db, project_id)
    return git_service.commit(project.path, payload.files, payload.message)


@app.post("/projects/{project_id}/git/push")
def project_git_push(project_id: int, payload: schemas.GitPushRequest, db: Session = Depends(get_db)) -> dict:
    project = project_or_404(db, project_id)
    return git_service.push(project.path, payload.remote, payload.branch, payload.confirm)


@app.post("/projects/{project_id}/git/pull")
def project_git_pull(project_id: int, payload: schemas.GitPullRequest, db: Session = Depends(get_db)) -> dict:
    project = project_or_404(db, project_id)
    return git_service.pull(project.path, payload.remote, payload.branch)


@app.get("/projects/{project_id}/git/pre-push-check")
def project_pre_push_check(project_id: int, db: Session = Depends(get_db)) -> dict:
    project = project_or_404(db, project_id)
    return git_service.pre_push_check(project.path)


@app.post("/projects/{project_id}/publish-github")
def publish_github(project_id: int, payload: schemas.ProjectPublishRequest, db: Session = Depends(get_db)) -> dict:
    project = project_or_404(db, project_id)
    config = settings_service.github_config(db)
    token = config.get("token")
    if not token:
        raise HTTPException(status_code=400, detail="GitHub token is not configured in Settings")
    if not git_service.is_git_repo(project.path):
        init_result = git_service.init_repo(project.path, payload.default_branch)
        if not init_result["ok"]:
            return init_result
    git_service.ensure_gitignore(project.path)
    scan = git_service.pre_push_check(project.path)
    if (scan["blocked_files"] or scan["secret_matches"]) and not payload.confirm_risks:
        return {"ok": False, "requires_confirmation": True, "scan": scan, "stderr": "Security check found risky files. Review before publishing."}
    if scan["safe_files"]:
        add_result = git_service.stage(project.path, scan["safe_files"])
        if not add_result["ok"]:
            return add_result
        commit_result = git_service.run_git(project.path, ["commit", "-m", payload.initial_commit_message], timeout=60)
        if not commit_result["ok"] and "nothing to commit" not in commit_result.get("stdout", "") + commit_result.get("stderr", ""):
            return commit_result
    owner = config.get("default_owner") or config.get("username")
    try:
        repo = github_service.create_repository(str(token), owner, payload.repository_name, payload.description, payload.visibility == "private", payload.default_branch)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    remote_url = repo.get("ssh_url") or repo.get("clone_url")
    if not git_service.status(project.path).get("remote_url") and remote_url:
        remote_result = git_service.run_git(project.path, ["remote", "add", "origin", remote_url])
        if not remote_result["ok"]:
            return remote_result
    push_result = git_service.push(project.path, "origin", payload.default_branch, True)
    if push_result["ok"]:
        project.remote_url = remote_url
        project.branch = payload.default_branch
        project.default_branch = payload.default_branch
        db.commit()
    return {"ok": push_result["ok"], "repo": repo, "remote_url": remote_url, "push": push_result, "scan": scan}


@app.get("/projects/{project_id}/versions")
def project_versions(project_id: int, db: Session = Depends(get_db)) -> list[dict]:
    project = project_or_404(db, project_id)
    return git_service.history(project.path)


@app.get("/projects/{project_id}/versions/{commit_hash}")
def project_version_detail(project_id: int, commit_hash: str, db: Session = Depends(get_db)) -> dict:
    project = project_or_404(db, project_id)
    return git_service.commit_detail(project.path, commit_hash)


@app.post("/projects/{project_id}/versions/{commit_hash}/open")
def project_open_version(project_id: int, commit_hash: str, db: Session = Depends(get_db)) -> dict:
    project = project_or_404(db, project_id)
    return git_service.open_version(project.path, commit_hash)


@app.post("/projects/{project_id}/versions/{commit_hash}/branch")
def project_branch_from_version(project_id: int, commit_hash: str, payload: schemas.BranchCreateRequest, db: Session = Depends(get_db)) -> dict:
    project = project_or_404(db, project_id)
    return git_service.create_branch_from(project.path, payload.name, commit_hash)


@app.post("/projects/{project_id}/versions/{commit_hash}/restore")
def project_restore_version(project_id: int, commit_hash: str, payload: schemas.VersionRestoreRequest, db: Session = Depends(get_db)) -> dict:
    project = project_or_404(db, project_id)
    return git_service.restore_to(project.path, commit_hash, payload.confirm, payload.create_backup_branch)


@app.get("/projects/{project_id}/branches")
def project_branches(project_id: int, db: Session = Depends(get_db)) -> dict:
    project = project_or_404(db, project_id)
    return git_service.branches(project.path)


@app.post("/projects/{project_id}/branches")
def project_create_branch(project_id: int, payload: schemas.BranchCreateRequest, db: Session = Depends(get_db)) -> dict:
    project = project_or_404(db, project_id)
    return git_service.create_branch_from(project.path, payload.name, payload.commit_hash)


@app.post("/projects/{project_id}/checkpoints", response_model=schemas.ProjectCheckpointOut)
def create_checkpoint(project_id: int, payload: schemas.ProjectCheckpointCreate, db: Session = Depends(get_db)):
    if payload.project_id != project_id:
        raise HTTPException(status_code=400, detail="Checkpoint project_id does not match URL")
    return crud.create_item(db, models.ProjectCheckpoint, payload)


@app.get("/tasks", response_model=list[schemas.TaskOut])
def list_tasks(db: Session = Depends(get_db)):
    return crud.list_items(db, models.Task)


@app.post("/tasks", response_model=schemas.TaskOut)
def create_task(payload: schemas.TaskCreate, db: Session = Depends(get_db)):
    task = crud.create_item(db, models.Task, payload)
    if task.project_id:
        project_progress_service.sync_project_progress(db, project_or_404(db, task.project_id))
    return task


@app.patch("/tasks/{task_id}", response_model=schemas.TaskOut)
def update_task(task_id: int, payload: schemas.TaskUpdate, db: Session = Depends(get_db)):
    task = crud.update_item(db, models.Task, task_id, payload)
    if task.project_id:
        project_progress_service.sync_project_progress(db, project_or_404(db, task.project_id))
    return task


@app.delete("/tasks/{task_id}")
def delete_task(task_id: int, db: Session = Depends(get_db)):
    task = project_or_none = db.get(models.Task, task_id)
    project_id = task.project_id if task else None
    result = crud.delete_item(db, models.Task, task_id)
    if project_id:
        project_progress_service.sync_project_progress(db, project_or_404(db, project_id))
    return result


@app.post("/papers/search", response_model=SearchResponse)
async def search_papers(request: SearchRequest) -> SearchResponse:
    openalex_papers = await search_openalex(request)
    crossref_papers = await search_crossref(request)
    papers_by_key = {}
    for paper in [*crossref_papers, *openalex_papers]:
        key = (paper.doi or paper.id).lower()
        current = papers_by_key.get(key)
        papers_by_key[key] = merge_search_papers(current, paper) if current else paper
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
def list_papers(venue: str | None = None, status: str | None = None, queue: bool = False, db: Session = Depends(get_db)):
    query = db.query(models.Paper)
    if venue:
        query = query.filter(models.Paper.venue == venue)
    if status:
        query = query.filter(func.lower(models.Paper.status) == normalize_paper_status(status).lower())
    if queue:
        query = query.filter(models.Paper.queued_at.is_not(None))
        query = query.order_by(models.Paper.priority.asc(), models.Paper.queued_at.asc())
    else:
        query = query.order_by(models.Paper.updated_at.desc())
    return query.limit(300).all()


@app.post("/papers", response_model=schemas.PaperOut)
def create_paper(payload: schemas.PaperCreate, db: Session = Depends(get_db)):
    data = payload.model_dump()
    data["status"] = normalize_paper_status(data.get("status"))
    data["reading_mode"] = normalize_reading_mode(data.get("reading_mode"))
    data["doi"] = normalize_doi(data.get("doi"))
    data["venue"] = normalize_venue(data.get("venue"))
    data["source_url"] = data.get("source_url") or data.get("url")
    return upsert_paper(db, data)


@app.post("/papers/candidate", response_model=schemas.PaperOut)
def save_candidate(payload: schemas.PaperLibraryImportRequest, db: Session = Depends(get_db)):
    data = search_paper_to_db_payload(payload.paper, "Candidate")
    data["priority"] = payload.priority
    data["reading_purpose"] = payload.reading_purpose
    data["related_project_id"] = payload.related_project_id
    if payload.related_project_id is not None:
        crud.get_item(db, models.Project, payload.related_project_id)
    return upsert_paper(db, data)


@app.post("/papers/library", response_model=schemas.PaperOut)
async def add_to_library(payload: schemas.PaperLibraryImportRequest, db: Session = Depends(get_db)):
    search_model = SearchPaperModel.model_validate(payload.paper)
    try:
        zotero_result = await import_to_zotero(ZoteroImportRequest(papers=[search_model]))
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    data = search_paper_to_db_payload(search_model, "To Read")
    data["priority"] = payload.priority
    data["reading_purpose"] = payload.reading_purpose
    data["related_project_id"] = payload.related_project_id
    if payload.related_project_id is not None:
        crud.get_item(db, models.Project, payload.related_project_id)
    apply_zotero_import_result_to_payload(db, data, zotero_result, 0)
    return upsert_paper(db, data)


@app.post("/papers/library/batch", response_model=list[schemas.PaperOut])
async def add_to_library_batch(payload: schemas.PaperLibraryBatchImportRequest, db: Session = Depends(get_db)):
    if not payload.papers:
        return []
    if payload.related_project_id is not None:
        crud.get_item(db, models.Project, payload.related_project_id)

    search_models = [SearchPaperModel.model_validate(paper) for paper in payload.papers]
    try:
        zotero_result = await import_to_zotero(ZoteroImportRequest(papers=search_models))
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    saved: list[models.Paper] = []
    for index, search_model in enumerate(search_models):
        data = search_paper_to_db_payload(search_model, "To Read")
        data["priority"] = payload.priority
        data["reading_purpose"] = payload.reading_purpose
        data["related_project_id"] = payload.related_project_id
        apply_zotero_import_result_to_payload(db, data, zotero_result, index)
        saved.append(upsert_paper(db, data))
    return saved


@app.post("/papers/{paper_id}/attach-pdf", response_model=schemas.PaperOut)
async def attach_pdf_to_paper(paper_id: int, payload: schemas.PaperPdfAttachRequest, db: Session = Depends(get_db)):
    paper = crud.get_item(db, models.Paper, paper_id)
    item_key = paper.zotero_item_key or paper.zotero_key
    if not item_key:
        raise HTTPException(status_code=400, detail="该文献尚未关联 Zotero 条目，不能挂载 PDF。")
    try:
        result = await attach_pdf_to_zotero(ZoteroAttachPdfRequest(
            item_key=item_key,
            pdf_url=payload.pdf_url or paper.pdf_url or paper.url,
            filename=payload.filename or f"{paper.title}.pdf",
            content_type=payload.content_type or "application/pdf",
            content_base64=payload.content_base64,
            source="LOCAL_FILE",
        ))
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if result.get("status") in {"ok", "skipped"}:
        apply_pdf_state(
            paper,
            status="ATTACHED",
            source=result.get("pdf_source") or "LOCAL_FILE",
            attachment_key=result.get("attachment_key"),
        )
        db.commit()
        db.refresh(paper)
    return paper


@app.patch("/papers/{paper_id}", response_model=schemas.PaperOut)
def update_paper(paper_id: int, payload: schemas.PaperUpdate, db: Session = Depends(get_db)):
    if payload.status is not None:
        payload.status = normalize_paper_status(payload.status)
    if payload.reading_mode is not None:
        payload.reading_mode = normalize_reading_mode(payload.reading_mode)
    if payload.doi is not None:
        payload.doi = normalize_doi(payload.doi)
    data = payload.model_dump(exclude_unset=True)
    if "url" in data and "source_url" not in data:
        data["source_url"] = data.get("url")
    item = crud.get_item(db, models.Paper, paper_id)
    for key, value in data.items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


@app.post("/papers/{paper_id}/zotero", response_model=schemas.PaperOut)
async def add_existing_paper_to_zotero(paper_id: int, db: Session = Depends(get_db)):
    paper = crud.get_item(db, models.Paper, paper_id)
    zotero_result = await import_to_zotero(ZoteroImportRequest(papers=[db_paper_to_search_model(paper)]))
    apply_zotero_import_result_to_paper(db, paper, zotero_result, 0)
    paper.status = "To Read"
    db.commit()
    db.refresh(paper)
    return paper


@app.post("/papers/{paper_id}/zotero/check", response_model=schemas.PaperOut)
async def check_paper_zotero_attachment(paper_id: int, db: Session = Depends(get_db)):
    paper = crud.get_item(db, models.Paper, paper_id)
    item_key = paper.zotero_item_key or paper.zotero_key
    if not item_key:
        apply_pdf_state(
            paper,
            status="NONE",
            error_code="PDF_NOT_FOUND",
            error_message="This paper is not linked to a Zotero item.",
        )
        db.commit()
        db.refresh(paper)
        return paper
    try:
        state = await get_zotero_item_sync_state(item_key)
    except Exception as exc:
        apply_pdf_state(
            paper,
            status="FAILED",
            error_code="ZOTERO_NOT_RUNNING",
            error_message=str(exc),
        )
        db.commit()
        db.refresh(paper)
        return paper
    apply_zotero_sync_state_to_paper(paper, state)
    db.commit()
    db.refresh(paper)
    return paper


@app.get("/papers/{paper_id}/open-links")
def paper_open_links(paper_id: int, db: Session = Depends(get_db)) -> dict:
    paper = crud.get_item(db, models.Paper, paper_id)
    item_key = paper.zotero_item_key or paper.zotero_key
    attachment_key = paper.zotero_attachment_key
    return {
        "article_url": paper.url or paper.source_url or (f"https://doi.org/{paper.doi}" if paper.doi else None),
        "zotero_item_uri": f"zotero://select/library/items/{item_key}" if item_key else None,
        "zotero_attachment_uri": f"zotero://select/library/items/{attachment_key}" if attachment_key else None,
    }


@app.post("/zotero/sync")
async def sync_zotero_papers(db: Session = Depends(get_db)) -> dict:
    papers = db.query(models.Paper).filter(or_(models.Paper.zotero_item_key.is_not(None), models.Paper.zotero_key.is_not(None))).all()
    synced = 0
    failed: list[dict[str, str]] = []
    for paper in papers:
        item_key = paper.zotero_item_key or paper.zotero_key
        if not item_key:
            continue
        try:
            state = await get_zotero_item_sync_state(item_key)
        except Exception as exc:
            failed.append({"item_key": item_key, "title": paper.title, "error": str(exc)})
            continue
        apply_zotero_sync_state_to_paper(paper, state)
        if state.get("title"):
            paper.title = state["title"]
        if state.get("doi"):
            synced_doi = normalize_doi(state["doi"])
            duplicate = db.query(models.Paper).filter(models.Paper.doi == synced_doi, models.Paper.id != paper.id).first() if synced_doi else None
            if synced_doi and duplicate is None:
                paper.doi = synced_doi
        if state.get("url"):
            paper.url = state["url"]
        if state.get("abstract") and not paper.abstract:
            paper.abstract = state["abstract"]
        if state.get("year"):
            paper.year = state["year"]
        if state.get("venue"):
            paper.venue = normalize_venue(state["venue"])
        synced += 1
    db.commit()
    return {"status": "ok", "synced": synced, "failed": failed, "message": f"已同步 Zotero：{synced} 篇文献。"}


@app.post("/papers/{paper_id}/queue", response_model=schemas.PaperOut)
def queue_paper(paper_id: int, payload: schemas.PaperQueueRequest, db: Session = Depends(get_db)):
    paper = crud.get_item(db, models.Paper, paper_id)
    if payload.related_project_id is not None:
        crud.get_item(db, models.Project, payload.related_project_id)
    paper.status = "To Read" if normalize_paper_status(paper.status) in {"Inbox", "Candidate"} else normalize_paper_status(paper.status)
    paper.priority = payload.priority
    paper.reading_purpose = payload.reading_purpose
    paper.related_project_id = payload.related_project_id
    paper.reading_mode = normalize_reading_mode(payload.reading_mode)
    paper.queued_at = paper.queued_at or datetime.utcnow()
    db.commit()
    db.refresh(paper)
    return paper


@app.get("/papers/{paper_id}/detail")
def paper_detail(paper_id: int, db: Session = Depends(get_db)) -> dict:
    paper = crud.get_item(db, models.Paper, paper_id)
    notes = db.query(models.ReadingNote).filter(models.ReadingNote.paper_id == paper_id).order_by(models.ReadingNote.updated_at.desc()).all()
    sessions = db.query(models.FocusSession).filter(models.FocusSession.paper_id == paper_id, models.FocusSession.status != "CANCELLED").all()
    knowledge = [{"id": item.id, "title": item.title, "area": item.area} for item in paper.knowledge_links]
    return {
        "paper": schemas.PaperOut.model_validate(paper).model_dump(mode="json"),
        "reading_notes": [schemas.ReadingNoteOut.model_validate(note).model_dump(mode="json") for note in notes],
        "reading_time_seconds": sum(focus_elapsed_seconds(session) for session in sessions),
        "knowledge_links": knowledge,
    }


@app.delete("/papers/{paper_id}")
def delete_paper(paper_id: int, db: Session = Depends(get_db)):
    return crud.delete_item(db, models.Paper, paper_id)


@app.get("/reading-notes", response_model=list[schemas.ReadingNoteOut])
def list_reading_notes(paper_id: int | None = None, db: Session = Depends(get_db)):
    query = db.query(models.ReadingNote)
    if paper_id is not None:
        query = query.filter(models.ReadingNote.paper_id == paper_id)
    return query.order_by(models.ReadingNote.updated_at.desc()).limit(300).all()


@app.post("/reading-notes", response_model=schemas.ReadingNoteOut)
def create_reading_note(payload: schemas.ReadingNoteCreate, db: Session = Depends(get_db)):
    data = payload.model_dump()
    paper = db.get(models.Paper, data["paper_id"]) if data.get("paper_id") else None
    if data.get("paper_id") and not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
    if not data.get("content_markdown") and data.get("content"):
        data["content_markdown"] = data["content"]
    if not data.get("content_markdown"):
        data["content_markdown"] = reading_note_template(paper)
    data["content"] = data.get("content_markdown") or data.get("content") or ""
    if paper:
        data["reading_status_snapshot"] = data.get("reading_status_snapshot") or paper.status
        data["reading_mode"] = data.get("reading_mode") or paper.reading_mode
        data["related_project_id"] = data.get("related_project_id") or paper.related_project_id
    item = models.ReadingNote(**data)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@app.post("/papers/{paper_id}/reading-note", response_model=schemas.ReadingNoteOut)
def create_or_get_paper_note(paper_id: int, db: Session = Depends(get_db)):
    paper = crud.get_item(db, models.Paper, paper_id)
    existing = db.query(models.ReadingNote).filter(models.ReadingNote.paper_id == paper_id).order_by(models.ReadingNote.updated_at.desc()).first()
    if existing:
        return existing
    item = models.ReadingNote(
        paper_id=paper.id,
        title=f"Reading Note - {paper.title[:220]}",
        status="draft",
        content=reading_note_template(paper),
        content_markdown=reading_note_template(paper),
        reading_status_snapshot=paper.status,
        reading_mode=paper.reading_mode,
        related_project_id=paper.related_project_id,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@app.patch("/reading-notes/{note_id}", response_model=schemas.ReadingNoteOut)
def update_reading_note(note_id: int, payload: schemas.ReadingNoteUpdate, db: Session = Depends(get_db)):
    item = crud.get_item(db, models.ReadingNote, note_id)
    data = payload.model_dump(exclude_unset=True)
    if "content_markdown" in data and "content" not in data:
        data["content"] = data["content_markdown"]
    if "content" in data and "content_markdown" not in data:
        data["content_markdown"] = data["content"]
    for key, value in data.items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


@app.get("/reading-notes/{note_id}/export", response_model=schemas.ReadingNoteExportOut)
def export_reading_note(note_id: int, db: Session = Depends(get_db)):
    note = crud.get_item(db, models.ReadingNote, note_id)
    paper = note.paper
    title = paper.title if paper else note.title
    metadata = [
        "---",
        f"title: {title}",
        f"paper_id: {note.paper_id or ''}",
        f"zotero_item_key: {(paper.zotero_item_key or paper.zotero_key) if paper else ''}",
        f"reading_status: {note.reading_status_snapshot or (paper.status if paper else '')}",
        f"reading_mode: {note.reading_mode or (paper.reading_mode if paper else '') or ''}",
        "---",
        "",
    ]
    return {"filename": safe_markdown_filename(title), "content": "\n".join(metadata) + note_content(note)}


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


# Compatibility APIs kept from the Dashboard/Settings/Focus phase.
PROJECT_STATUSES_LOWER = ["planning", "active", "blocked", "paused", "completed", "archived"]
PAPER_STATUSES = ["Inbox", "Candidate", "To Read", "Skimming", "Reading", "Deep Reading", "Finished", "Reference", "Dropped"]
EXPERIMENT_STATUSES = ["running", "pending", "completed", "failed"]
DASHBOARD_VENUES = ["ICRA", "IROS", "RA-L", "T-RO", "Science Robotics"]
DEFAULT_FLAT_SETTINGS = {
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
    return item.value if item and item.value is not None else DEFAULT_FLAT_SETTINGS.get(key, "")


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


def build_settings_payload(db: Session) -> dict[str, Any]:
    zotero_key = secret_value(db, "integrations.zotero.api_key")
    github_token = secret_value(db, "integrations.github.personal_access_token")
    return {
        "general": {"language": setting_value(db, "general.language")},
        "paths": {
            "projects_root": setting_value(db, "paths.projects_root"),
            "knowledge_root": setting_value(db, "paths.knowledge_root"),
            "obsidian_vault": setting_value(db, "paths.obsidian_vault"),
            "dataset_root": setting_value(db, "paths.dataset_root"),
            "experiment_root": setting_value(db, "paths.experiment_root"),
        },
        "integrations": {
            "obsidian": {
                "enabled": parse_bool(setting_value(db, "integrations.obsidian.enabled")),
                "vault_path": setting_value(db, "integrations.obsidian.vault_path"),
                "knowledge_root": setting_value(db, "integrations.obsidian.knowledge_root"),
                "use_obsidian_uri": parse_bool(setting_value(db, "integrations.obsidian.use_obsidian_uri")),
            },
            "zotero": {
                "enabled": parse_bool(setting_value(db, "integrations.zotero.enabled")),
                "connection_mode": setting_value(db, "integrations.zotero.connection_mode"),
                "user_id": setting_value(db, "integrations.zotero.user_id"),
                "api_key": None,
                "api_key_masked": mask_secret(zotero_key),
                "library": setting_value(db, "integrations.zotero.library"),
            },
            "github": {
                "enabled": parse_bool(setting_value(db, "integrations.github.enabled")),
                "username": setting_value(db, "integrations.github.username"),
                "personal_access_token": None,
                "personal_access_token_masked": mask_secret(github_token),
                "default_owner": setting_value(db, "integrations.github.default_owner"),
                "default_branch": setting_value(db, "integrations.github.default_branch"),
            },
        },
    }


def store_settings_payload(db: Session, payload: dict[str, Any]) -> dict[str, Any]:
    general = payload.get("general") or {}
    if "language" in general:
        put_setting(db, "general.language", str(general["language"]))
    for key, value in (payload.get("paths") or {}).items():
        put_setting(db, f"paths.{key}", str(value))
    integrations = payload.get("integrations") or {}
    obsidian = integrations.get("obsidian") or {}
    for key in ["vault_path", "knowledge_root"]:
        if key in obsidian:
            put_setting(db, f"integrations.obsidian.{key}", str(obsidian[key]))
    for key in ["enabled", "use_obsidian_uri"]:
        if key in obsidian:
            put_setting(db, f"integrations.obsidian.{key}", bool_to_setting(bool(obsidian[key])))
    zotero = integrations.get("zotero") or {}
    for key in ["connection_mode", "user_id", "library"]:
        if key in zotero:
            put_setting(db, f"integrations.zotero.{key}", str(zotero[key]))
    if "enabled" in zotero:
        put_setting(db, "integrations.zotero.enabled", bool_to_setting(bool(zotero["enabled"])))
    put_secret(db, "integrations.zotero.api_key", zotero.get("api_key"))
    github = integrations.get("github") or {}
    for key in ["username", "default_owner", "default_branch"]:
        if key in github:
            put_setting(db, f"integrations.github.{key}", str(github[key]))
    if "enabled" in github:
        put_setting(db, "integrations.github.enabled", bool_to_setting(bool(github["enabled"])))
    put_secret(db, "integrations.github.personal_access_token", github.get("personal_access_token"))
    db.commit()
    return build_settings_payload(db)


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
    experiment_counts = {status: 0 for status in EXPERIMENT_STATUSES}
    for experiment in experiments:
        experiment_counts[infer_experiment_status(experiment)] += 1
    settings_payload = build_settings_payload(db)
    current_session = current_focus_session(db)
    return {
        "today": {"date": today, "tasks": [schemas.TaskOut.model_validate(task).model_dump(mode="json") for task in today_tasks], "completed_tasks": sum(1 for task in today_tasks if task.status == "done"), "total_tasks": len(today_tasks), "completion_rate": 0, "courses": [], "schedule": [], "plan": [task.title for task in today_tasks if task.status != "done"][:5]},
        "projects": {"total": len(projects), "counts": project_counts, "featured": featured[:6]},
        "papers": {"total": len(papers), "status_counts": paper_status_counts, "venue_counts": venue_counts, "currently_reading": currently_reading[:6], "recently_finished": recently_finished[:6]},
        "experiments": {"total": len(experiments), "counts": experiment_counts, "running": [], "recent_results": [], "research_ideas_pending": db.query(models.ResearchIdea).filter(models.ResearchIdea.status == "candidate").count(), "research_ideas": []},
        "knowledge": {"obsidian_connected": bool(settings_payload["integrations"]["obsidian"]["enabled"] and settings_payload["integrations"]["obsidian"]["vault_path"]), "total_notes": db.query(models.KnowledgeLink).count(), "updated_this_week": 0, "recently_updated": []},
        "git": {"projects": []},
        "focus": {"current_session": focus_out(current_session), "today_duration": focus_duration_for_range(db, "today"), "week_duration": focus_duration_for_range(db, "week")},
        "attention": [],
    }


@app.get("/api/dashboard/summary")
def api_dashboard_summary(db: Session = Depends(get_db)) -> dict:
    return build_dashboard_summary_payload(db)


@app.get("/api/settings")
def api_get_settings(db: Session = Depends(get_db)) -> dict:
    return build_settings_payload(db)


@app.patch("/api/settings")
def api_update_settings(payload: dict[str, Any], db: Session = Depends(get_db)) -> dict:
    return store_settings_payload(db, payload)


@app.get("/api/focus/current")
def api_get_current_focus(db: Session = Depends(get_db)) -> dict:
    return {"current_session": focus_out(current_focus_session(db))}


@app.post("/api/focus/start")
def api_start_focus(payload: dict[str, Any], db: Session = Depends(get_db)) -> dict:
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


@app.post("/api/focus/{session_id}/pause")
def api_pause_focus(session_id: int, db: Session = Depends(get_db)) -> dict:
    session = crud.get_item(db, models.FocusSession, session_id)
    if session.status != "RUNNING":
        raise HTTPException(status_code=400, detail="Only a running focus session can be paused")
    session.status = "PAUSED"
    session.paused_started_at = datetime.utcnow()
    db.commit()
    db.refresh(session)
    return focus_out(session)


@app.post("/api/focus/{session_id}/resume")
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


@app.post("/api/focus/{session_id}/finish")
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


@app.get("/api/focus/stats")
def api_focus_stats(range: str = "today", db: Session = Depends(get_db)) -> dict:
    if range not in {"today", "week", "month"}:
        raise HTTPException(status_code=400, detail="Unsupported range")
    return {"range": range, "duration_seconds": focus_duration_for_range(db, range)}


@app.get("/project-progress")
def list_project_progress(date: str | None = None, project_id: int | None = None, db: Session = Depends(get_db)):
    query = db.query(models.ProjectProgressLog)
    if date:
        query = query.filter(models.ProjectProgressLog.date == date)
    if project_id:
        query = query.filter(models.ProjectProgressLog.project_id == project_id)
    return query.order_by(models.ProjectProgressLog.date.desc(), models.ProjectProgressLog.id.desc()).limit(300).all()


@app.post("/project-progress")
def create_project_progress(payload: dict[str, Any], db: Session = Depends(get_db)):
    crud.get_item(db, models.Project, payload["project_id"])
    item = models.ProjectProgressLog(**payload)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@app.patch("/project-progress/{log_id}")
def update_project_progress(log_id: int, payload: dict[str, Any], db: Session = Depends(get_db)):
    item = crud.get_item(db, models.ProjectProgressLog, log_id)
    for key, value in payload.items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


@app.delete("/project-progress/{log_id}")
def delete_project_progress(log_id: int, db: Session = Depends(get_db)):
    return crud.delete_item(db, models.ProjectProgressLog, log_id)
