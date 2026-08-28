from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Project(Base, TimestampMixin):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    path: Mapped[str] = mapped_column(String(800), unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(40), default="Active")
    progress: Mapped[float] = mapped_column(Float, default=0)
    progress_mode: Mapped[str] = mapped_column(String(40), default="AUTO")
    project_type: Mapped[str | None] = mapped_column(String(120))
    tags: Mapped[str | None] = mapped_column(Text)
    current_stage: Mapped[str | None] = mapped_column(String(240))
    next_stage: Mapped[str | None] = mapped_column(String(240))
    health: Mapped[str | None] = mapped_column(String(40))
    remote_url: Mapped[str | None] = mapped_column(String(800))
    branch: Mapped[str | None] = mapped_column(String(200))
    default_branch: Mapped[str | None] = mapped_column(String(200))
    experiment_dir: Mapped[str | None] = mapped_column(String(800))
    results_dir: Mapped[str | None] = mapped_column(String(800))
    links: Mapped[str | None] = mapped_column(Text)

    stages: Mapped[list["ProjectStage"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    milestones: Mapped[list["Milestone"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    tasks: Mapped[list["Task"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    experiments: Mapped[list["Experiment"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    checkpoints: Mapped[list["ProjectCheckpoint"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    progress_logs: Mapped[list["ProjectProgressLog"]] = relationship(back_populates="project", cascade="all, delete-orphan")


class ProjectStage(Base, TimestampMixin):
    __tablename__ = "project_stages"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    title: Mapped[str] = mapped_column(String(240))
    status: Mapped[str] = mapped_column(String(40), default="pending")
    weight: Mapped[float] = mapped_column(Float, default=1)
    progress: Mapped[float] = mapped_column(Float, default=0)
    order_index: Mapped[int] = mapped_column(Integer, default=0)

    project: Mapped[Project] = relationship(back_populates="stages")
    milestones: Mapped[list["Milestone"]] = relationship(back_populates="stage")


class Milestone(Base, TimestampMixin):
    __tablename__ = "milestones"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    stage_id: Mapped[int | None] = mapped_column(ForeignKey("project_stages.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(240))
    status: Mapped[str] = mapped_column(String(40), default="pending")
    weight: Mapped[float] = mapped_column(Float, default=1)
    progress: Mapped[float] = mapped_column(Float, default=0)
    order_index: Mapped[int] = mapped_column(Integer, default=0)

    project: Mapped[Project] = relationship(back_populates="milestones")
    stage: Mapped[ProjectStage | None] = relationship(back_populates="milestones")
    tasks: Mapped[list["Task"]] = relationship(back_populates="milestone")


class Task(Base, TimestampMixin):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), nullable=True)
    milestone_id: Mapped[int | None] = mapped_column(ForeignKey("milestones.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(240))
    status: Mapped[str] = mapped_column(String(40), default="todo")
    priority: Mapped[str] = mapped_column(String(40), default="medium")
    due_date: Mapped[str | None] = mapped_column(String(40))
    notes: Mapped[str | None] = mapped_column(Text)

    project: Mapped[Project | None] = relationship(back_populates="tasks")
    milestone: Mapped[Milestone | None] = relationship(back_populates="tasks")
    focus_sessions: Mapped[list["FocusSession"]] = relationship(back_populates="task")


class ProjectProgressLog(Base, TimestampMixin):
    __tablename__ = "project_progress_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    date: Mapped[str] = mapped_column(String(40), index=True)
    stage: Mapped[str | None] = mapped_column(String(160))
    completed: Mapped[str] = mapped_column(Text, default="")
    pending: Mapped[str] = mapped_column(Text, default="")
    progress_note: Mapped[str | None] = mapped_column(Text)

    project: Mapped[Project] = relationship(back_populates="progress_logs")


class Paper(Base, TimestampMixin):
    __tablename__ = "papers"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(800), index=True)
    translated_title: Mapped[str | None] = mapped_column(String(800))
    abstract: Mapped[str | None] = mapped_column(Text)
    translated_abstract: Mapped[str | None] = mapped_column(Text)
    authors: Mapped[str | None] = mapped_column(Text)
    year: Mapped[int | None] = mapped_column(Integer)
    venue: Mapped[str] = mapped_column(String(80), default="Others", index=True)
    tags: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(40), default="inbox")
    priority: Mapped[str] = mapped_column(String(40), default="normal")
    doi: Mapped[str | None] = mapped_column(String(200), unique=True)
    url: Mapped[str | None] = mapped_column(String(1000))
    pdf_url: Mapped[str | None] = mapped_column(String(1000))
    zotero_key: Mapped[str | None] = mapped_column(String(80))
    related_project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), nullable=True)

    reading_notes: Mapped[list["ReadingNote"]] = relationship(back_populates="paper", cascade="all, delete-orphan")


class ReadingNote(Base, TimestampMixin):
    __tablename__ = "reading_notes"

    id: Mapped[int] = mapped_column(primary_key=True)
    paper_id: Mapped[int | None] = mapped_column(ForeignKey("papers.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(400))
    status: Mapped[str] = mapped_column(String(40), default="draft")
    content: Mapped[str] = mapped_column(Text, default="")
    extracted_knowledge: Mapped[str | None] = mapped_column(Text)
    idea: Mapped[str | None] = mapped_column(Text)

    paper: Mapped[Paper | None] = relationship(back_populates="reading_notes")


class ResearchIdea(Base, TimestampMixin):
    __tablename__ = "research_ideas"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(300))
    source: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(40), default="candidate")
    content: Mapped[str] = mapped_column(Text, default="")


class Experiment(Base, TimestampMixin):
    __tablename__ = "experiments"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), nullable=True)
    code: Mapped[str] = mapped_column(String(80), index=True)
    title: Mapped[str] = mapped_column(String(300))
    date: Mapped[str | None] = mapped_column(String(40))
    git_commit: Mapped[str | None] = mapped_column(String(80))
    git_branch: Mapped[str | None] = mapped_column(String(200))
    config_path: Mapped[str | None] = mapped_column(String(800))
    dataset: Mapped[str | None] = mapped_column(String(300))
    metrics: Mapped[str | None] = mapped_column(Text)
    result: Mapped[str | None] = mapped_column(Text)
    conclusion: Mapped[str | None] = mapped_column(Text)

    project: Mapped[Project | None] = relationship(back_populates="experiments")


class ProjectCheckpoint(Base, TimestampMixin):
    __tablename__ = "project_checkpoints"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    name: Mapped[str] = mapped_column(String(240))
    description: Mapped[str | None] = mapped_column(Text)
    commit_hash: Mapped[str] = mapped_column(String(80))
    experiment_id: Mapped[int | None] = mapped_column(ForeignKey("experiments.id"), nullable=True)
    tags: Mapped[str | None] = mapped_column(Text)

    project: Mapped[Project] = relationship(back_populates="checkpoints")


class KnowledgeLink(Base, TimestampMixin):
    __tablename__ = "knowledge_links"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(300))
    area: Mapped[str] = mapped_column(String(120), default="Embodied AI")
    obsidian_uri: Mapped[str | None] = mapped_column(String(1000))
    vault_path: Mapped[str | None] = mapped_column(String(1000))
    tags: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)


class DashboardLayout(Base, TimestampMixin):
    __tablename__ = "dashboard_layouts"

    id: Mapped[str] = mapped_column(String(80), primary_key=True, default="default")
    layout_json: Mapped[str] = mapped_column(Text, default="[]")


class SystemSetting(Base, TimestampMixin):
    __tablename__ = "system_settings"

    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    value: Mapped[str | None] = mapped_column(Text)


class SecretSetting(Base, TimestampMixin):
    __tablename__ = "secret_settings"

    key: Mapped[str] = mapped_column(String(160), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")


class FocusSession(Base, TimestampMixin):
    __tablename__ = "focus_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0)
    paused_seconds: Mapped[int] = mapped_column(Integer, default=0)
    paused_started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="RUNNING", index=True)
    task_id: Mapped[int | None] = mapped_column(ForeignKey("tasks.id"), nullable=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), nullable=True)
    note: Mapped[str | None] = mapped_column(Text)

    task: Mapped[Task | None] = relationship(back_populates="focus_sessions")
    project: Mapped[Project | None] = relationship()
