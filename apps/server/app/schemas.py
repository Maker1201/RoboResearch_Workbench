from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

PROJECT_STATUSES = {"Planning", "Active", "Blocked", "Paused", "Completed", "Archived"}
PROGRESS_MODES = {"AUTO", "MANUAL"}
PAPER_READING_STATUSES = {"Inbox", "Candidate", "To Read", "Skimming", "Reading", "Deep Reading", "Finished", "Reference", "Dropped"}
READING_MODES = {"SCAN", "SKIM", "READ", "DEEP"}
READING_PURPOSES = {"Project", "Literature Review", "Learn Method", "Reproduce", "Compare Baseline", "Research Idea", "General Interest"}


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ProjectBase(BaseModel):
    name: str
    path: str
    description: str | None = None
    status: str = "Active"
    progress: float = Field(default=0, ge=0, le=100)
    progress_mode: str = "AUTO"
    project_type: str | None = None
    tags: str | None = None
    current_stage: str | None = None
    next_stage: str | None = None
    health: str | None = None
    remote_url: str | None = None
    branch: str | None = None
    default_branch: str | None = None
    experiment_dir: str | None = None
    results_dir: str | None = None
    links: str | None = None


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    name: str | None = None
    path: str | None = None
    description: str | None = None
    status: str | None = None
    progress: float | None = Field(default=None, ge=0, le=100)
    progress_mode: str | None = None
    project_type: str | None = None
    tags: str | None = None
    current_stage: str | None = None
    next_stage: str | None = None
    health: str | None = None
    remote_url: str | None = None
    branch: str | None = None
    default_branch: str | None = None
    experiment_dir: str | None = None
    results_dir: str | None = None
    links: str | None = None


class ProjectOut(ProjectBase, ORMModel):
    id: int
    created_at: datetime
    updated_at: datetime


class ProjectStageBase(BaseModel):
    project_id: int
    title: str
    status: str = "pending"
    weight: float = 1
    progress: float = Field(default=0, ge=0, le=100)
    order_index: int = 0


class ProjectStageCreate(ProjectStageBase):
    pass


class ProjectStageUpdate(BaseModel):
    title: str | None = None
    status: str | None = None
    weight: float | None = None
    progress: float | None = Field(default=None, ge=0, le=100)
    order_index: int | None = None


class ProjectStageOut(ProjectStageBase, ORMModel):
    id: int
    created_at: datetime
    updated_at: datetime


class MilestoneBase(BaseModel):
    project_id: int
    stage_id: int | None = None
    title: str
    status: str = "pending"
    weight: float = 1
    progress: float = Field(default=0, ge=0, le=100)
    order_index: int = 0


class MilestoneCreate(MilestoneBase):
    pass


class MilestoneUpdate(BaseModel):
    stage_id: int | None = None
    title: str | None = None
    status: str | None = None
    weight: float | None = None
    progress: float | None = Field(default=None, ge=0, le=100)
    order_index: int | None = None


class MilestoneOut(MilestoneBase, ORMModel):
    id: int
    created_at: datetime
    updated_at: datetime


class TaskBase(BaseModel):
    project_id: int | None = None
    milestone_id: int | None = None
    title: str
    status: str = "todo"
    priority: str = "medium"
    due_date: str | None = None
    notes: str | None = None


class TaskCreate(TaskBase):
    pass


class TaskUpdate(BaseModel):
    project_id: int | None = None
    milestone_id: int | None = None
    title: str | None = None
    status: str | None = None
    priority: str | None = None
    due_date: str | None = None
    notes: str | None = None


class TaskOut(TaskBase, ORMModel):
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
    status: str = "Inbox"
    reading_mode: str | None = None
    priority: str = "normal"
    reading_purpose: str | None = None
    queued_at: datetime | None = None
    doi: str | None = None
    url: str | None = None
    source_url: str | None = None
    pdf_url: str | None = None
    zotero_key: str | None = None
    zotero_item_key: str | None = None
    zotero_attachment_key: str | None = None
    zotero_library: str | None = None
    zotero_pdf_attached: bool = False
    zotero_pdf_status: str | None = None
    pdf_status: str = "NONE"
    pdf_source: str | None = None
    pdf_last_checked_at: datetime | None = None
    pdf_error_code: str | None = None
    pdf_error_message: str | None = None
    zotero_synced_at: datetime | None = None
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
    reading_mode: str | None = None
    priority: str | None = None
    reading_purpose: str | None = None
    queued_at: datetime | None = None
    doi: str | None = None
    url: str | None = None
    source_url: str | None = None
    pdf_url: str | None = None
    zotero_key: str | None = None
    zotero_item_key: str | None = None
    zotero_attachment_key: str | None = None
    zotero_library: str | None = None
    zotero_pdf_attached: bool | None = None
    zotero_pdf_status: str | None = None
    pdf_status: str | None = None
    pdf_source: str | None = None
    pdf_last_checked_at: datetime | None = None
    pdf_error_code: str | None = None
    pdf_error_message: str | None = None
    zotero_synced_at: datetime | None = None
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
    content_markdown: str = ""
    reading_status_snapshot: str | None = None
    reading_mode: str | None = None
    one_sentence_summary: str | None = None
    relevance_to_me: str | None = None
    extracted_knowledge: str | None = None
    idea: str | None = None
    related_project_id: int | None = None


class ReadingNoteCreate(ReadingNoteBase):
    pass


class ReadingNoteUpdate(BaseModel):
    paper_id: int | None = None
    title: str | None = None
    status: str | None = None
    content: str | None = None
    content_markdown: str | None = None
    reading_status_snapshot: str | None = None
    reading_mode: str | None = None
    one_sentence_summary: str | None = None
    relevance_to_me: str | None = None
    extracted_knowledge: str | None = None
    idea: str | None = None
    related_project_id: int | None = None


class ReadingNoteOut(ReadingNoteBase, ORMModel):
    id: int
    created_at: datetime
    updated_at: datetime




class PaperQueueRequest(BaseModel):
    priority: str = "normal"
    reading_purpose: str = "General Interest"
    related_project_id: int | None = None
    reading_mode: str | None = None


class PaperLibraryImportRequest(BaseModel):
    paper: dict[str, Any]
    reading_purpose: str | None = None
    related_project_id: int | None = None
    priority: str = "normal"


class PaperLibraryBatchImportRequest(BaseModel):
    papers: list[dict[str, Any]]
    reading_purpose: str | None = None
    related_project_id: int | None = None
    priority: str = "normal"


class PaperPdfAttachRequest(BaseModel):
    pdf_url: str | None = None
    filename: str | None = None
    content_type: str = "application/pdf"
    content_base64: str


class ReadingNoteExportOut(BaseModel):
    filename: str
    content: str

class ExperimentBase(BaseModel):
    project_id: int | None = None
    code: str
    title: str
    date: str | None = None
    git_commit: str | None = None
    git_branch: str | None = None
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
    git_branch: str | None = None
    config_path: str | None = None
    dataset: str | None = None
    metrics: str | None = None
    result: str | None = None
    conclusion: str | None = None


class ExperimentOut(ExperimentBase, ORMModel):
    id: int
    created_at: datetime
    updated_at: datetime


class ProjectCheckpointBase(BaseModel):
    project_id: int
    name: str
    description: str | None = None
    commit_hash: str
    experiment_id: int | None = None
    tags: str | None = None


class ProjectCheckpointCreate(ProjectCheckpointBase):
    pass


class ProjectCheckpointOut(ProjectCheckpointBase, ORMModel):
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


class GitStageRequest(BaseModel):
    files: list[str] = Field(min_length=1)


class GitPullRequest(BaseModel):
    remote: str = "origin"
    branch: str | None = None


class ProjectScanRequest(BaseModel):
    path: str


class ProjectRegisterRequest(BaseModel):
    path: str
    name: str | None = None
    description: str | None = None
    status: str = "Active"
    progress_mode: str = "AUTO"
    tags: str | None = None


class ProjectPublishRequest(BaseModel):
    repository_name: str
    description: str | None = None
    visibility: str = "private"
    default_branch: str = "main"
    initial_commit_message: str = "chore: initial workbench import"
    confirm_risks: bool = False


class VersionRestoreRequest(BaseModel):
    confirm: bool = False
    create_backup_branch: bool = True


class BranchCreateRequest(BaseModel):
    name: str
    commit_hash: str | None = None


class SystemSettingsIn(BaseModel):
    settings: dict[str, Any]


class SystemSettingsOut(BaseModel):
    settings: dict[str, Any]
