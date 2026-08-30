from __future__ import annotations

from pathlib import Path

from sqlalchemy import inspect, text

from . import models, project_scanner_service
from .database import Base, SessionLocal, engine, get_db
from .services.projects_service import create_default_stages


def init_database() -> None:
    Base.metadata.create_all(bind=engine)
    migrate_schema()
    seed_defaults()
    configure_integrations()


def configure_integrations() -> None:
    from .paper_integrations.zotero import configure_key_store
    from .services.settings_service import put_secret, secret_value

    def load_zotero_key() -> str | None:
        db = SessionLocal()
        try:
            return secret_value(db, "integrations.zotero.api_key") or None
        finally:
            db.close()

    def save_zotero_key(key: str) -> None:
        db = SessionLocal()
        try:
            put_secret(db, "integrations.zotero.api_key", key)
            db.commit()
        finally:
            db.close()

    configure_key_store(load_zotero_key, save_zotero_key)


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
