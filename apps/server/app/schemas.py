from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ProjectBase(BaseModel):
    name: str
    path: str
    description: str | None = None
    status: str = "active"
    progress: float = Field(default=0, ge=0, le=100)
    remote_url: str | None = None
    branch: str | None = None


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    name: str | None = None
    path: str | None = None
    description: str | None = None
    status: str | None = None
    progress: float | None = Field(default=None, ge=0, le=100)
    remote_url: str | None = None
    branch: str | None = None


class ProjectOut(ProjectBase, ORMModel):
    id: int
    created_at: datetime
    updated_at: datetime


class MilestoneBase(BaseModel):
    project_id: int
    title: str
    weight: float = 1
    progress: float = Field(default=0, ge=0, le=100)
    order_index: int = 0


class MilestoneCreate(MilestoneBase):
    pass


class MilestoneOut(MilestoneBase, ORMModel):
    id: int
    created_at: datetime
    updated_at: datetime


class TaskBase(BaseModel):
    project_id: int | None = None
    title: str
    status: str = "todo"
    priority: str = "medium"
    due_date: str | None = None
    notes: str | None = None


class TaskCreate(TaskBase):
    pass


class TaskUpdate(BaseModel):
    project_id: int | None = None
    title: str | None = None
    status: str | None = None
    priority: str | None = None
    due_date: str | None = None
    notes: str | None = None


class TaskOut(TaskBase, ORMModel):
    id: int
    created_at: datetime
    updated_at: datetime


class ProjectProgressLogBase(BaseModel):
    project_id: int
    date: str
    stage: str | None = None
    completed: str = ""
    pending: str = ""
    progress_note: str | None = None


class ProjectProgressLogCreate(ProjectProgressLogBase):
    pass


class ProjectProgressLogUpdate(BaseModel):
    project_id: int | None = None
    date: str | None = None
    stage: str | None = None
    completed: str | None = None
    pending: str | None = None
    progress_note: str | None = None


class ProjectProgressLogOut(ProjectProgressLogBase, ORMModel):
    id: int
    created_at: datetime
    updated_at: datetime


class PaperBase(BaseModel):
    title: str
    translated_title: str | None = None
    abstract: str | None = None
    translated_abstract: str | None = None
    authors: str | None = None
    year: int | None = None
    venue: str = "Others"
    tags: str | None = None
    status: str = "inbox"
    priority: str = "normal"
    doi: str | None = None
    url: str | None = None
    pdf_url: str | None = None
    zotero_key: str | None = None
    related_project_id: int | None = None


class PaperCreate(PaperBase):
    pass


class PaperUpdate(BaseModel):
    title: str | None = None
    translated_title: str | None = None
    abstract: str | None = None
    translated_abstract: str | None = None
    authors: str | None = None
    year: int | None = None
    venue: str | None = None
    tags: str | None = None
    status: str | None = None
    priority: str | None = None
    doi: str | None = None
    url: str | None = None
    pdf_url: str | None = None
    zotero_key: str | None = None
    related_project_id: int | None = None


class PaperOut(PaperBase, ORMModel):
    id: int
    created_at: datetime
    updated_at: datetime


class ReadingNoteBase(BaseModel):
    paper_id: int | None = None
    title: str
    status: str = "draft"
    content: str = ""
    extracted_knowledge: str | None = None
    idea: str | None = None


class ReadingNoteCreate(ReadingNoteBase):
    pass


class ReadingNoteUpdate(BaseModel):
    paper_id: int | None = None
    title: str | None = None
    status: str | None = None
    content: str | None = None
    extracted_knowledge: str | None = None
    idea: str | None = None


class ReadingNoteOut(ReadingNoteBase, ORMModel):
    id: int
    created_at: datetime
    updated_at: datetime


class ExperimentBase(BaseModel):
    project_id: int | None = None
    code: str
    title: str
    date: str | None = None
    git_commit: str | None = None
    config_path: str | None = None
    dataset: str | None = None
    metrics: str | None = None
    result: str | None = None
    conclusion: str | None = None


class ExperimentCreate(ExperimentBase):
    pass


class ExperimentUpdate(BaseModel):
    project_id: int | None = None
    code: str | None = None
    title: str | None = None
    date: str | None = None
    git_commit: str | None = None
    config_path: str | None = None
    dataset: str | None = None
    metrics: str | None = None
    result: str | None = None
    conclusion: str | None = None


class ExperimentOut(ExperimentBase, ORMModel):
    id: int
    created_at: datetime
    updated_at: datetime


class KnowledgeLinkBase(BaseModel):
    title: str
    area: str = "Embodied AI"
    obsidian_uri: str | None = None
    vault_path: str | None = None
    tags: str | None = None
    notes: str | None = None


class KnowledgeLinkCreate(KnowledgeLinkBase):
    pass


class KnowledgeLinkUpdate(BaseModel):
    title: str | None = None
    area: str | None = None
    obsidian_uri: str | None = None
    vault_path: str | None = None
    tags: str | None = None
    notes: str | None = None


class KnowledgeLinkOut(KnowledgeLinkBase, ORMModel):
    id: int
    created_at: datetime
    updated_at: datetime


class DashboardLayoutIn(BaseModel):
    layout: list[dict[str, Any]]


class DashboardLayoutOut(BaseModel):
    layout: list[dict[str, Any]]


class GitCommitRequest(BaseModel):
    files: list[str] = Field(min_length=1)
    message: str = Field(min_length=3, max_length=300)


class GitPushRequest(BaseModel):
    remote: str = "origin"
    branch: str | None = None
    confirm: bool = False




class GeneralSettings(BaseModel):
    language: str = "zh-CN"


class PathSettings(BaseModel):
    projects_root: str = "/home/robot"
    knowledge_root: str = "/home/robot/文档/Obsidian Vault"
    obsidian_vault: str = "/home/robot/文档/Obsidian Vault"
    dataset_root: str = "/home/robot/datasets"
    experiment_root: str = "/home/robot/experiments"


class ObsidianSettings(BaseModel):
    enabled: bool = False
    vault_path: str = ""
    knowledge_root: str = "Knowledge"
    use_obsidian_uri: bool = True


class ZoteroSettings(BaseModel):
    enabled: bool = False
    connection_mode: str = "web_api"
    user_id: str = ""
    api_key: str | None = None
    api_key_masked: str | None = None
    library: str = "My Library"


class GitHubSettings(BaseModel):
    enabled: bool = False
    username: str = ""
    personal_access_token: str | None = None
    personal_access_token_masked: str | None = None
    default_owner: str = ""
    default_branch: str = "main"


class IntegrationSettings(BaseModel):
    obsidian: ObsidianSettings = Field(default_factory=ObsidianSettings)
    zotero: ZoteroSettings = Field(default_factory=ZoteroSettings)
    github: GitHubSettings = Field(default_factory=GitHubSettings)


class SystemSettingsOut(BaseModel):
    general: GeneralSettings = Field(default_factory=GeneralSettings)
    paths: PathSettings = Field(default_factory=PathSettings)
    integrations: IntegrationSettings = Field(default_factory=IntegrationSettings)


class SystemSettingsUpdate(BaseModel):
    general: GeneralSettings | None = None
    paths: PathSettings | None = None
    integrations: IntegrationSettings | None = None


class SettingsTestResult(BaseModel):
    ok: bool
    message: str


class FocusSessionCreate(BaseModel):
    task_id: int | None = None
    project_id: int | None = None
    note: str | None = None


class FocusSessionOut(ORMModel):
    id: int
    started_at: datetime
    ended_at: datetime | None = None
    duration_seconds: int
    paused_seconds: int
    status: str
    task_id: int | None = None
    project_id: int | None = None
    note: str | None = None
    created_at: datetime
    updated_at: datetime
    elapsed_seconds: int = 0
    task_title: str | None = None
    project_name: str | None = None


class FocusStatsOut(BaseModel):
    range: str
    duration_seconds: int


class DashboardSummaryOut(BaseModel):
    today: dict[str, Any]
    projects: dict[str, Any]
    papers: dict[str, Any]
    experiments: dict[str, Any]
    knowledge: dict[str, Any]
    git: dict[str, Any]
    focus: dict[str, Any]
    attention: list[dict[str, Any]]
