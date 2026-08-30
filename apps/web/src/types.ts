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
