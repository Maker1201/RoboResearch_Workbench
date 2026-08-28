export type Project = {
  id: number;
  name: string;
  path: string;
  description?: string | null;
  status: string;
  progress: number;
  remote_url?: string | null;
  branch?: string | null;
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
  priority: string;
  doi?: string | null;
  url?: string | null;
  pdf_url?: string | null;
  zotero_key?: string | null;
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
  extracted_knowledge?: string | null;
  idea?: string | null;
};

export type Experiment = {
  id: number;
  project_id?: number | null;
  code: string;
  title: string;
  date?: string | null;
  git_commit?: string | null;
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
  task_id?: number | null;
  project_id?: number | null;
  note?: string | null;
  created_at: string;
  updated_at: string;
  elapsed_seconds: number;
  task_title?: string | null;
  project_name?: string | null;
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
