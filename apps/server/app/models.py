from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Table, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


paper_knowledge_links = Table(
    "paper_knowledge_links",
    Base.metadata,
    Column("paper_id", ForeignKey("papers.id"), primary_key=True),
    Column("knowledge_id", ForeignKey("knowledge_links.id"), primary_key=True),
    Column("created_at", DateTime, default=datetime.utcnow),
)


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
    experiment_studies: Mapped[list["ExperimentStudy"]] = relationship(back_populates="project", cascade="all, delete-orphan")
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
    due_time: Mapped[str | None] = mapped_column(String(8))
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
    status: Mapped[str] = mapped_column(String(40), default="Inbox", index=True)
    reading_mode: Mapped[str | None] = mapped_column(String(40))
    priority: Mapped[str] = mapped_column(String(40), default="normal")
    reading_purpose: Mapped[str | None] = mapped_column(String(80))
    queued_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    doi: Mapped[str | None] = mapped_column(String(200), unique=True)
    url: Mapped[str | None] = mapped_column(String(1000))
    source_url: Mapped[str | None] = mapped_column(String(1000))
    pdf_url: Mapped[str | None] = mapped_column(String(1000))
    zotero_key: Mapped[str | None] = mapped_column(String(80))
    zotero_item_key: Mapped[str | None] = mapped_column(String(80), index=True)
    zotero_attachment_key: Mapped[str | None] = mapped_column(String(80), index=True)
    zotero_library: Mapped[str | None] = mapped_column(String(120))
    zotero_pdf_attached: Mapped[bool] = mapped_column(Boolean, default=False)
    zotero_pdf_status: Mapped[str | None] = mapped_column(String(80))
    pdf_status: Mapped[str] = mapped_column(String(80), default="NONE", index=True)
    pdf_source: Mapped[str | None] = mapped_column(String(80))
    pdf_last_checked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    pdf_error_code: Mapped[str | None] = mapped_column(String(120))
    pdf_error_message: Mapped[str | None] = mapped_column(String(500))
    zotero_synced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ai_summary: Mapped[str | None] = mapped_column(Text)
    ai_relevance: Mapped[float | None] = mapped_column(Float)
    ai_suggested_mode: Mapped[str | None] = mapped_column(String(40))
    ai_triaged_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    related_project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), nullable=True)

    reading_notes: Mapped[list["ReadingNote"]] = relationship(back_populates="paper", cascade="all, delete-orphan")
    related_project: Mapped[Project | None] = relationship()
    knowledge_links: Mapped[list["KnowledgeLink"]] = relationship(secondary=paper_knowledge_links, back_populates="papers")


class ReadingNote(Base, TimestampMixin):
    __tablename__ = "reading_notes"

    id: Mapped[int] = mapped_column(primary_key=True)
    paper_id: Mapped[int | None] = mapped_column(ForeignKey("papers.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(400))
    status: Mapped[str] = mapped_column(String(40), default="draft")
    content: Mapped[str] = mapped_column(Text, default="")
    content_markdown: Mapped[str] = mapped_column(Text, default="")
    reading_status_snapshot: Mapped[str | None] = mapped_column(String(40))
    reading_mode: Mapped[str | None] = mapped_column(String(40))
    one_sentence_summary: Mapped[str | None] = mapped_column(Text)
    relevance_to_me: Mapped[str | None] = mapped_column(Text)
    extracted_knowledge: Mapped[str | None] = mapped_column(Text)
    idea: Mapped[str | None] = mapped_column(Text)
    note_source: Mapped[str] = mapped_column(String(40), default="manual")
    zotero_note_key: Mapped[str | None] = mapped_column(String(80), index=True)
    zotero_note_synced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    related_project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), nullable=True)

    paper: Mapped[Paper | None] = relationship(back_populates="reading_notes")
    related_project: Mapped[Project | None] = relationship()


class ResearchIdea(Base, TimestampMixin):
    __tablename__ = "research_ideas"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(300))
    source: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(40), default="candidate")
    content: Mapped[str] = mapped_column(Text, default="")
    source_paper_id: Mapped[int | None] = mapped_column(ForeignKey("papers.id"), nullable=True)
    source_reading_note_id: Mapped[int | None] = mapped_column(ForeignKey("reading_notes.id"), nullable=True)
    related_project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), nullable=True)


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


class RobotProfile(Base, TimestampMixin):
    __tablename__ = "robot_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(240), index=True)
    robot_type: Mapped[str | None] = mapped_column(String(160))
    arms: Mapped[str | None] = mapped_column(String(240))
    sensors: Mapped[str | None] = mapped_column(Text)
    compute: Mapped[str | None] = mapped_column(String(240))
    ros_version: Mapped[str | None] = mapped_column(String(120))
    moveit_version: Mapped[str | None] = mapped_column(String(120))
    notes: Mapped[str | None] = mapped_column(Text)

    studies: Mapped[list["ExperimentStudy"]] = relationship(back_populates="robot_profile")


class ExperimentStudy(Base, TimestampMixin):
    __tablename__ = "experiment_studies"

    id: Mapped[int] = mapped_column(primary_key=True)
    study_code: Mapped[str] = mapped_column(String(80), index=True)
    name: Mapped[str] = mapped_column(String(300), index=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), nullable=True)
    robot_profile_id: Mapped[int | None] = mapped_column(ForeignKey("robot_profiles.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="Planning", index=True)
    current_stage: Mapped[str | None] = mapped_column(String(120))
    task_type: Mapped[str] = mapped_column(String(120), default="Robot Task Planning")
    environment: Mapped[str | None] = mapped_column(String(120))
    research_question: Mapped[str | None] = mapped_column(Text)
    hypothesis: Mapped[str | None] = mapped_column(Text)
    claim: Mapped[str | None] = mapped_column(Text)
    conclusion_status: Mapped[str] = mapped_column(String(40), default="Inconclusive")
    hypothesis_status: Mapped[str] = mapped_column(String(40), default="Inconclusive")
    evidence_summary: Mapped[str | None] = mapped_column(Text)
    key_metric_improvements: Mapped[str | None] = mapped_column(Text)
    next_step: Mapped[str | None] = mapped_column(Text)
    analysis_key_findings: Mapped[str | None] = mapped_column(Text)
    analysis_unexpected_findings: Mapped[str | None] = mapped_column(Text)
    analysis_failure_summary: Mapped[str | None] = mapped_column(Text)
    analysis_why_worked: Mapped[str | None] = mapped_column(Text)
    analysis_why_failed: Mapped[str | None] = mapped_column(Text)
    analysis_limitations: Mapped[str | None] = mapped_column(Text)
    analysis_threats_to_validity: Mapped[str | None] = mapped_column(Text)

    project: Mapped[Project | None] = relationship(back_populates="experiment_studies")
    robot_profile: Mapped[RobotProfile | None] = relationship(back_populates="studies")
    task_profile: Mapped["TaskProfile | None"] = relationship(back_populates="study", cascade="all, delete-orphan", uselist=False)
    protocol: Mapped["ExperimentProtocol | None"] = relationship(back_populates="study", cascade="all, delete-orphan", uselist=False)
    conditions: Mapped[list["ExperimentCondition"]] = relationship(back_populates="study", cascade="all, delete-orphan")
    metrics: Mapped[list["MetricValue"]] = relationship(back_populates="study", cascade="all, delete-orphan")
    artifacts: Mapped[list["ArtifactReference"]] = relationship(back_populates="study", cascade="all, delete-orphan")


class TaskProfile(Base, TimestampMixin):
    __tablename__ = "task_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    study_id: Mapped[int] = mapped_column(ForeignKey("experiment_studies.id"), unique=True)
    task_name: Mapped[str | None] = mapped_column(String(240))
    instruction: Mapped[str | None] = mapped_column(Text)
    initial_state: Mapped[str | None] = mapped_column(Text)
    goal_state: Mapped[str | None] = mapped_column(Text)
    constraints: Mapped[str | None] = mapped_column(Text)
    success_criteria: Mapped[str | None] = mapped_column(Text)
    task_steps: Mapped[str | None] = mapped_column(Text)
    task_complexity: Mapped[str | None] = mapped_column(String(80))
    scene_complexity: Mapped[str | None] = mapped_column(String(80))
    object_count: Mapped[int | None] = mapped_column(Integer)
    perception_uncertainty: Mapped[str | None] = mapped_column(String(80))
    execution_uncertainty: Mapped[str | None] = mapped_column(String(80))
    position_error_threshold: Mapped[str | None] = mapped_column(String(80))
    orientation_error_threshold: Mapped[str | None] = mapped_column(String(80))
    no_collision_required: Mapped[bool] = mapped_column(Boolean, default=True)
    timeout_required: Mapped[bool] = mapped_column(Boolean, default=True)
    human_intervention_allowed: Mapped[bool] = mapped_column(Boolean, default=False)

    study: Mapped[ExperimentStudy] = relationship(back_populates="task_profile")


class ExperimentProtocol(Base, TimestampMixin):
    __tablename__ = "experiment_protocols"

    id: Mapped[int] = mapped_column(primary_key=True)
    study_id: Mapped[int] = mapped_column(ForeignKey("experiment_studies.id"), unique=True)
    trials_per_condition: Mapped[int | None] = mapped_column(Integer)
    random_seeds: Mapped[str | None] = mapped_column(Text)
    seed_strategy: Mapped[str | None] = mapped_column(String(160))
    timeout_seconds: Mapped[int | None] = mapped_column(Integer)
    max_retries: Mapped[int | None] = mapped_column(Integer)
    human_intervention_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    reset_policy: Mapped[str | None] = mapped_column(Text)
    task_repetitions: Mapped[int | None] = mapped_column(Integer)
    scene_count: Mapped[int | None] = mapped_column(Integer)
    object_reset_policy: Mapped[str | None] = mapped_column(Text)

    study: Mapped[ExperimentStudy] = relationship(back_populates="protocol")


class AblationGroup(Base, TimestampMixin):
    __tablename__ = "ablation_groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    study_id: Mapped[int] = mapped_column(ForeignKey("experiment_studies.id"))
    name: Mapped[str] = mapped_column(String(240))
    description: Mapped[str | None] = mapped_column(Text)


class ExperimentCondition(Base, TimestampMixin):
    __tablename__ = "experiment_conditions"

    id: Mapped[int] = mapped_column(primary_key=True)
    study_id: Mapped[int] = mapped_column(ForeignKey("experiment_studies.id"))
    ablation_group_id: Mapped[int | None] = mapped_column(ForeignKey("ablation_groups.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(240))
    condition_type: Mapped[str] = mapped_column(String(80), default="Baseline")
    description: Mapped[str | None] = mapped_column(Text)
    enabled_components: Mapped[str | None] = mapped_column(Text)
    disabled_components: Mapped[str | None] = mapped_column(Text)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), nullable=True)
    git_commit_hash: Mapped[str | None] = mapped_column(String(80))
    git_branch: Mapped[str | None] = mapped_column(String(200))
    git_dirty: Mapped[bool] = mapped_column(Boolean, default=False)
    config_path: Mapped[str | None] = mapped_column(String(800))
    prompt_version: Mapped[str | None] = mapped_column(String(240))
    prompt_path: Mapped[str | None] = mapped_column(String(800))
    model_name: Mapped[str | None] = mapped_column(String(240))
    model_version: Mapped[str | None] = mapped_column(String(240))
    llm: Mapped[str | None] = mapped_column(String(240))
    retry_policy: Mapped[str | None] = mapped_column(String(240))
    timeout_seconds: Mapped[int | None] = mapped_column(Integer)
    simulator: Mapped[str | None] = mapped_column(String(160))
    ros_version: Mapped[str | None] = mapped_column(String(120))
    moveit_version: Mapped[str | None] = mapped_column(String(120))
    generalization_dimension: Mapped[str | None] = mapped_column(String(240))
    seen_unseen: Mapped[str | None] = mapped_column(String(80))

    study: Mapped[ExperimentStudy] = relationship(back_populates="conditions")
    trials: Mapped[list["ExperimentTrial"]] = relationship(back_populates="condition", cascade="all, delete-orphan")
    metrics: Mapped[list["MetricValue"]] = relationship(back_populates="condition", cascade="all, delete-orphan")
    artifacts: Mapped[list["ArtifactReference"]] = relationship(back_populates="condition", cascade="all, delete-orphan")


class ExperimentTrial(Base, TimestampMixin):
    __tablename__ = "experiment_trials"

    id: Mapped[int] = mapped_column(primary_key=True)
    condition_id: Mapped[int] = mapped_column(ForeignKey("experiment_conditions.id"))
    trial_id: Mapped[str] = mapped_column(String(80), index=True)
    scene: Mapped[str | None] = mapped_column(String(240))
    seed: Mapped[int | None] = mapped_column(Integer)
    start_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    end_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float)
    result: Mapped[str] = mapped_column(String(40), default="Success")
    steps: Mapped[int | None] = mapped_column(Integer)
    plan_length: Mapped[int | None] = mapped_column(Integer)
    replan_count: Mapped[int | None] = mapped_column(Integer, default=0)
    human_intervention: Mapped[bool] = mapped_column(Boolean, default=False)
    failure_category: Mapped[str | None] = mapped_column(String(120))
    failure_layer: Mapped[str | None] = mapped_column(String(120))
    note: Mapped[str | None] = mapped_column(Text)

    condition: Mapped[ExperimentCondition] = relationship(back_populates="trials")
    trace_events: Mapped[list["PlanningTraceEvent"]] = relationship(back_populates="trial", cascade="all, delete-orphan")
    metrics: Mapped[list["MetricValue"]] = relationship(back_populates="trial", cascade="all, delete-orphan")
    artifacts: Mapped[list["ArtifactReference"]] = relationship(back_populates="trial", cascade="all, delete-orphan")


class MetricDefinition(Base, TimestampMixin):
    __tablename__ = "metric_definitions"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(240))
    name_zh: Mapped[str | None] = mapped_column(String(240))
    group: Mapped[str] = mapped_column(String(120), default="Task-level")
    unit: Mapped[str | None] = mapped_column(String(80))
    higher_is_better: Mapped[bool] = mapped_column(Boolean, default=True)
    description: Mapped[str | None] = mapped_column(Text)


class MetricValue(Base, TimestampMixin):
    __tablename__ = "metric_values"

    id: Mapped[int] = mapped_column(primary_key=True)
    study_id: Mapped[int | None] = mapped_column(ForeignKey("experiment_studies.id"), nullable=True)
    condition_id: Mapped[int | None] = mapped_column(ForeignKey("experiment_conditions.id"), nullable=True)
    trial_id: Mapped[int | None] = mapped_column(ForeignKey("experiment_trials.id"), nullable=True)
    metric_key: Mapped[str] = mapped_column(String(160), index=True)
    value: Mapped[float | None] = mapped_column(Float)
    value_text: Mapped[str | None] = mapped_column(String(240))
    mean: Mapped[float | None] = mapped_column(Float)
    std: Mapped[float | None] = mapped_column(Float)
    count: Mapped[int | None] = mapped_column(Integer)
    p_value: Mapped[float | None] = mapped_column(Float)
    effect_size: Mapped[str | None] = mapped_column(String(120))
    confidence_interval: Mapped[str | None] = mapped_column(String(120))
    statistical_test: Mapped[str | None] = mapped_column(String(160))
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)

    study: Mapped[ExperimentStudy | None] = relationship(back_populates="metrics")
    condition: Mapped[ExperimentCondition | None] = relationship(back_populates="metrics")
    trial: Mapped[ExperimentTrial | None] = relationship(back_populates="metrics")


class PlanningTraceEvent(Base, TimestampMixin):
    __tablename__ = "planning_trace_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    trial_id: Mapped[int] = mapped_column(ForeignKey("experiment_trials.id"))
    event_type: Mapped[str] = mapped_column(String(80))
    title: Mapped[str | None] = mapped_column(String(240))
    content: Mapped[str | None] = mapped_column(Text)
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    timestamp: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    trial: Mapped[ExperimentTrial] = relationship(back_populates="trace_events")


class ArtifactReference(Base, TimestampMixin):
    __tablename__ = "artifact_references"

    id: Mapped[int] = mapped_column(primary_key=True)
    study_id: Mapped[int | None] = mapped_column(ForeignKey("experiment_studies.id"), nullable=True)
    condition_id: Mapped[int | None] = mapped_column(ForeignKey("experiment_conditions.id"), nullable=True)
    trial_id: Mapped[int | None] = mapped_column(ForeignKey("experiment_trials.id"), nullable=True)
    artifact_type: Mapped[str] = mapped_column(String(80), default="log")
    path: Mapped[str] = mapped_column(String(1000))
    size: Mapped[int | None] = mapped_column(Integer)
    description: Mapped[str | None] = mapped_column(Text)

    study: Mapped[ExperimentStudy | None] = relationship(back_populates="artifacts")
    condition: Mapped[ExperimentCondition | None] = relationship(back_populates="artifacts")
    trial: Mapped[ExperimentTrial | None] = relationship(back_populates="artifacts")


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
    papers: Mapped[list[Paper]] = relationship(secondary=paper_knowledge_links, back_populates="knowledge_links")


class ZoteroAnnotationCache(Base, TimestampMixin):
    __tablename__ = "zotero_annotation_cache"

    id: Mapped[int] = mapped_column(primary_key=True)
    paper_id: Mapped[int] = mapped_column(ForeignKey("papers.id"), index=True)
    zotero_item_key: Mapped[str] = mapped_column(String(80), index=True)
    zotero_annotation_key: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    annotation_type: Mapped[str] = mapped_column(String(40), default="highlight")
    selected_text: Mapped[str | None] = mapped_column(Text)
    comment: Mapped[str | None] = mapped_column(Text)
    page_label: Mapped[str | None] = mapped_column(String(80))
    page_index: Mapped[int | None] = mapped_column(Integer)
    tags: Mapped[str | None] = mapped_column(Text)
    date_modified: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    paper: Mapped[Paper] = relationship()


class KnowledgeInboxItem(Base, TimestampMixin):
    __tablename__ = "knowledge_inbox_items"
    __table_args__ = (
        UniqueConstraint("source_type", "zotero_annotation_key", "inbox_type", name="uq_knowledge_inbox_zotero_annotation_type"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source_type: Mapped[str] = mapped_column(String(80), default="ZOTERO_ANNOTATION", index=True)
    source_paper_id: Mapped[int | None] = mapped_column(ForeignKey("papers.id"), nullable=True, index=True)
    zotero_item_key: Mapped[str | None] = mapped_column(String(80), index=True)
    zotero_annotation_key: Mapped[str | None] = mapped_column(String(80), index=True)
    inbox_type: Mapped[str] = mapped_column(String(40), default="knowledge", index=True)
    selected_text: Mapped[str | None] = mapped_column(Text)
    comment: Mapped[str | None] = mapped_column(Text)
    page_label: Mapped[str | None] = mapped_column(String(80))
    tags: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(40), default="pending", index=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    paper: Mapped[Paper | None] = relationship()


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
    focus_type: Mapped[str | None] = mapped_column(String(80))
    context_type: Mapped[str | None] = mapped_column(String(80))
    task_id: Mapped[int | None] = mapped_column(ForeignKey("tasks.id"), nullable=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), nullable=True)
    paper_id: Mapped[int | None] = mapped_column(ForeignKey("papers.id"), nullable=True)
    reading_note_id: Mapped[int | None] = mapped_column(ForeignKey("reading_notes.id"), nullable=True)
    note: Mapped[str | None] = mapped_column(Text)

    task: Mapped[Task | None] = relationship(back_populates="focus_sessions")
    project: Mapped[Project | None] = relationship()
    paper: Mapped[Paper | None] = relationship()
    reading_note: Mapped[ReadingNote | None] = relationship()
