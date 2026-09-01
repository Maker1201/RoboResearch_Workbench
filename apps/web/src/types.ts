export type Project = {
  id: number;
  name: string;
  path: string;
  description?: string | null;
  status: string;
  progress: number;
  progress_mode?: "AUTO" | "MANUAL" | string;
  project_type?: string | null;
  tags?: string | null;
  current_stage?: string | null;
  next_stage?: string | null;
  health?: string | null;
  remote_url?: string | null;
  branch?: string | null;
  default_branch?: string | null;
  experiment_dir?: string | null;
  results_dir?: string | null;
  links?: string | null;
};


export type ProjectProgressLog = {
  id: number;
  project_id: number;
  date: string;
  stage?: string | null;
  completed: string;
  pending: string;
  progress_note?: string | null;
};

export type DirectoryListing = {
  path: string;
  parent?: string | null;
  items: { name: string; path: string; is_dir: boolean }[];
};

export type ProjectStage = {
  id?: number;
  project_id?: number;
  title: string;
  status: string;
  weight: number;
  progress: number;
  order_index: number;
  milestones?: MilestoneProgress[];
};

export type MilestoneProgress = {
  id: number;
  title: string;
  status: string;
  weight: number;
  progress: number;
  order_index: number;
  tasks_total: number;
  tasks_done: number;
};

export type ProjectProgress = {
  project_id: number;
  mode: string;
  progress: number;
  current_stage?: string | null;
  next_stage?: string | null;
  computed_current_stage?: string | null;
  computed_next_stage?: string | null;
  stages: ProjectStage[];
  orphan_milestones: MilestoneProgress[];
};

export type ProjectScan = {
  name: string;
  path: string;
  description?: string | null;
  project_type: string;
  tags: string[];
  detections: Record<string, boolean>;
  git: any;
  branch?: string | null;
  remote_url?: string | null;
  readme?: string | null;
  registration_case: string;
  suggested_stages: ProjectStage[];
};

export type GitCommit = {
  hash: string;
  short_hash: string;
  author?: string | null;
  date?: string | null;
  message?: string | null;
  stats?: string | null;
};

export type Task = {
  id: number;
  project_id?: number | null;
  title: string;
  status: string;
  priority: string;
  due_date?: string | null;
  due_time?: string | null;
  notes?: string | null;
};

export type Paper = {
  id: number;
  title: string;
  translated_title?: string | null;
  abstract?: string | null;
  translated_abstract?: string | null;
  authors?: string | null;
  year?: number | null;
  venue: string;
  tags?: string | null;
  status: string;
  reading_mode?: string | null;
  priority: string;
  reading_purpose?: string | null;
  queued_at?: string | null;
  doi?: string | null;
  url?: string | null;
  source_url?: string | null;
  pdf_url?: string | null;
  zotero_key?: string | null;
  zotero_item_key?: string | null;
  zotero_attachment_key?: string | null;
  zotero_library?: string | null;
  zotero_pdf_attached?: boolean;
  zotero_pdf_status?: string | null;
  pdf_status?: string | null;
  pdf_source?: string | null;
  pdf_last_checked_at?: string | null;
  pdf_error_code?: string | null;
  pdf_error_message?: string | null;
  zotero_synced_at?: string | null;
  ai_summary?: string | null;
  ai_relevance?: number | null;
  ai_suggested_mode?: string | null;
  ai_triaged_at?: string | null;
  related_project_id?: number | null;
};

export type SearchPaper = {
  id: string;
  title: string;
  translated_title?: string | null;
  abstract?: string | null;
  translated_abstract?: string | null;
  authors: string[];
  year?: number | null;
  venue?: string | null;
  source_id?: string | null;
  source_label?: string | null;
  doi?: string | null;
  url?: string | null;
  pdf_url?: string | null;
  is_oa: boolean;
  relevance: number;
  matched_keywords: string[];
  in_library?: boolean | null;
  library_paper_id?: number | null;
  library_status?: string | null;
  library_pdf_status?: string | null;
  in_zotero?: boolean | null;
  zotero_item_key?: string | null;
};

export type ReadingNote = {
  id: number;
  paper_id?: number | null;
  title: string;
  status: string;
  content: string;
  content_markdown?: string | null;
  reading_status_snapshot?: string | null;
  reading_mode?: string | null;
  one_sentence_summary?: string | null;
  relevance_to_me?: string | null;
  extracted_knowledge?: string | null;
  idea?: string | null;
  note_source?: string | null;
  zotero_note_key?: string | null;
  zotero_note_synced_at?: string | null;
  related_project_id?: number | null;
};

export type Experiment = {
  id: number;
  project_id?: number | null;
  code: string;
  title: string;
  date?: string | null;
  git_commit?: string | null;
  git_branch?: string | null;
  config_path?: string | null;
  dataset?: string | null;
  metrics?: string | null;
  result?: string | null;
  conclusion?: string | null;
};


export type RobotProfile = {
  id: number;
  name: string;
  robot_type?: string | null;
  arms?: string | null;
  sensors?: string | null;
  compute?: string | null;
  ros_version?: string | null;
  moveit_version?: string | null;
  notes?: string | null;
};

export type TaskProfile = {
  id?: number;
  study_id?: number;
  task_name?: string | null;
  instruction?: string | null;
  initial_state?: string | null;
  goal_state?: string | null;
  constraints?: string | null;
  success_criteria?: string | null;
  task_steps?: string | null;
  task_complexity?: string | null;
  scene_complexity?: string | null;
  object_count?: number | null;
  perception_uncertainty?: string | null;
  execution_uncertainty?: string | null;
  position_error_threshold?: string | null;
  orientation_error_threshold?: string | null;
  no_collision_required?: boolean;
  timeout_required?: boolean;
  human_intervention_allowed?: boolean;
};

export type ExperimentProtocol = {
  id?: number;
  study_id?: number;
  trials_per_condition?: number | null;
  random_seeds?: string | null;
  seed_strategy?: string | null;
  timeout_seconds?: number | null;
  max_retries?: number | null;
  human_intervention_allowed?: boolean;
  reset_policy?: string | null;
  task_repetitions?: number | null;
  scene_count?: number | null;
  object_reset_policy?: string | null;
};

export type ExperimentStudy = {
  id: number;
  study_code: string;
  name: string;
  project_id?: number | null;
  robot_profile_id?: number | null;
  status: string;
  current_stage?: string | null;
  task_type: string;
  environment?: string | null;
  research_question?: string | null;
  hypothesis?: string | null;
  claim?: string | null;
  conclusion_status: string;
  hypothesis_status: string;
  evidence_summary?: string | null;
  key_metric_improvements?: string | null;
  next_step?: string | null;
  analysis_key_findings?: string | null;
  analysis_unexpected_findings?: string | null;
  analysis_failure_summary?: string | null;
  analysis_why_worked?: string | null;
  analysis_why_failed?: string | null;
  analysis_limitations?: string | null;
  analysis_threats_to_validity?: string | null;
  conditions_count?: number;
  trials_count?: number;
  primary_metric?: string | null;
  project_name?: string | null;
  robot_name?: string | null;
  created_at?: string;
  updated_at?: string;
};

export type ExperimentCondition = {
  id: number;
  study_id: number;
  ablation_group_id?: number | null;
  name: string;
  condition_type: string;
  description?: string | null;
  enabled_components?: string | null;
  disabled_components?: string | null;
  project_id?: number | null;
  git_commit_hash?: string | null;
  git_branch?: string | null;
  git_dirty?: boolean;
  config_path?: string | null;
  prompt_version?: string | null;
  prompt_path?: string | null;
  model_name?: string | null;
  model_version?: string | null;
  llm?: string | null;
  retry_policy?: string | null;
  timeout_seconds?: number | null;
  simulator?: string | null;
  ros_version?: string | null;
  moveit_version?: string | null;
  generalization_dimension?: string | null;
  seen_unseen?: string | null;
  trials_count?: number;
  success_rate?: number | null;
};

export type ExperimentTrial = {
  id: number;
  condition_id: number;
  trial_id: string;
  scene?: string | null;
  seed?: number | null;
  start_time?: string | null;
  end_time?: string | null;
  duration_seconds?: number | null;
  result: string;
  steps?: number | null;
  plan_length?: number | null;
  replan_count?: number | null;
  human_intervention?: boolean;
  failure_category?: string | null;
  failure_layer?: string | null;
  note?: string | null;
};

export type MetricValue = {
  id: number;
  study_id?: number | null;
  condition_id?: number | null;
  trial_id?: number | null;
  metric_key: string;
  value?: number | null;
  value_text?: string | null;
  mean?: number | null;
  std?: number | null;
  count?: number | null;
  p_value?: number | null;
  effect_size?: string | null;
  confidence_interval?: string | null;
  statistical_test?: string | null;
  is_primary?: boolean;
};

export type PlanningTraceEvent = {
  id: number;
  trial_id: number;
  event_type: string;
  title?: string | null;
  content?: string | null;
  order_index: number;
  timestamp?: string | null;
};

export type ArtifactReference = {
  id: number;
  study_id?: number | null;
  condition_id?: number | null;
  trial_id?: number | null;
  artifact_type: string;
  path: string;
  size?: number | null;
  description?: string | null;
};

export type AblationGroup = {
  id: number;
  study_id: number;
  name: string;
  description?: string | null;
};

export type ExperimentStudyDetail = {
  study: ExperimentStudy;
  task_profile?: TaskProfile | null;
  protocol?: ExperimentProtocol | null;
  robot_profile?: RobotProfile | null;
  conditions: ExperimentCondition[];
  trials: ExperimentTrial[];
  metrics: MetricValue[];
  trace_events: PlanningTraceEvent[];
  artifacts: ArtifactReference[];
  ablation_groups: AblationGroup[];
  failure_summary: Record<string, number>;
  result_summary: Record<string, { trials: number; success: number; failed: number; aborted: number }>;
};

export type MetricTemplate = {
  key: string;
  name: string;
  name_zh?: string | null;
  group: string;
  unit?: string | null;
  higher_is_better?: boolean;
};

export type KnowledgeLink = {
  id: number;
  title: string;
  area: string;
  obsidian_uri?: string | null;
  vault_path?: string | null;
  tags?: string | null;
  notes?: string | null;
};

export type Summary = {
  projects: number;
  active_projects: number;
  tasks_total: number;
  tasks_done: number;
  papers: number;
  reading_notes: number;
  experiments: number;
  knowledge_links: number;
  papers_by_venue: Record<string, number>;
};



export type FocusStatus = "RUNNING" | "PAUSED" | "COMPLETED" | "CANCELLED";

export type FocusSession = {
  id: number;
  started_at: string;
  ended_at?: string | null;
  duration_seconds: number;
  paused_seconds: number;
  status: FocusStatus;
  focus_type?: string | null;
  context_type?: string | null;
  task_id?: number | null;
  project_id?: number | null;
  paper_id?: number | null;
  reading_note_id?: number | null;
  note?: string | null;
  created_at: string;
  updated_at: string;
  elapsed_seconds: number;
  task_title?: string | null;
  project_name?: string | null;
  paper_title?: string | null;
  reading_note_title?: string | null;
};

export type SystemSettings = {
  general: { language: "zh-CN" | "en-US" | string };
  paths: {
    projects_root: string;
    knowledge_root: string;
    obsidian_vault: string;
    dataset_root: string;
    experiment_root: string;
  };
  integrations: {
    obsidian: {
      enabled: boolean;
      vault_path: string;
      knowledge_root: string;
      use_obsidian_uri: boolean;
    };
    zotero: {
      enabled: boolean;
      connection_mode: string;
      user_id: string;
      api_key?: string | null;
      api_key_masked?: string | null;
      library: string;
      data_dir?: string | null;
    };
    ai: {
      provider: string;
      api_base: string;
      api_key?: string | null;
      api_key_masked?: string | null;
      model: string;
      output_language: string;
      research_interests: string;
      max_pdf_chars: number;
    };
    github: {
      enabled: boolean;
      username: string;
      personal_access_token?: string | null;
      personal_access_token_masked?: string | null;
      default_owner: string;
      default_branch: string;
    };
  };
};

export type DashboardSummary = {
  today: {
    date: string;
    tasks: Task[];
    completed_tasks: number;
    total_tasks: number;
    completion_rate: number;
    courses: string[];
    schedule: string[];
    plan: string[];
  };
  projects: {
    total: number;
    counts: Record<string, number>;
    featured: Array<{
      id: number;
      name: string;
      status: string;
      progress: number;
      current_milestone?: string | null;
      next_milestone?: string | null;
    }>;
  };
  papers: {
    total: number;
    status_counts: Record<string, number>;
    venue_counts: Record<string, number>;
    currently_reading: Paper[];
    recently_finished: Paper[];
  };
  experiments: {
    total: number;
    counts: Record<string, number>;
    running: Experiment[];
    recent_results: Experiment[];
    research_ideas_pending: number;
    research_ideas: string[];
  };
  knowledge: {
    obsidian_connected: boolean;
    total_notes: number;
    updated_this_week: number;
    recently_updated: KnowledgeLink[];
  };
  git: {
    projects: Array<{
      project_id: number;
      project_name: string;
      branch?: string | null;
      modified_files: number;
      unpushed_commits: number;
      last_commit?: string | null;
      ok: boolean;
      error?: string;
    }>;
  };
  focus: {
    current_session?: FocusSession | null;
    today_duration: number;
    week_duration: number;
  };
  attention: Array<{
    kind: string;
    severity: string;
    title: string;
    message: string;
  }>;
};

export type GitChange = {
  path: string;
  status: string;
};

export type GitStatusInfo = {
  is_repo: boolean;
  branch?: string | null;
  remote_url?: string | null;
  changes: GitChange[];
  modified: number;
  untracked: number;
  conflicts: number;
  unpushed_commits: number;
  last_commit?: string | null;
  recent_commits: string[];
};

export type GitSecurityScan = {
  ok?: boolean;
  safe_files?: string[];
  blocked_files?: string[];
  large_files?: Array<{ path: string; size?: number }>;
  secret_matches?: Array<{ path: string; reason?: string }>;
};

export type GitActionResult = {
  ok?: boolean;
  stderr?: string;
  scan?: GitSecurityScan | null;
};

export type ProjectCheckpoint = {
  id: number;
  project_id: number;
  name: string;
  commit_hash: string;
  experiment_id?: number | null;
  tags?: string | null;
};

export type ProjectDetail = {
  project: Project;
  progress?: ProjectProgress;
  git?: GitStatusInfo;
  experiments?: Experiment[];
  checkpoints?: ProjectCheckpoint[];
};

export type GitVersionDetail = GitCommit & {
  diff?: string | null;
};
