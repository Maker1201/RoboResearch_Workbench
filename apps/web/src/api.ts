import type { DashboardSummary, DirectoryListing, Experiment, FocusSession, GitCommit, KnowledgeLink, Paper, Project, ProjectProgress, ProjectProgressLog, ProjectScan, ReadingNote, SearchPaper, Summary, SystemSettings, Task } from "./types";

export const API_BASE = import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8770";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || response.statusText);
  }
  return response.json();
}

export const api = {
  health: () => request<{ ok: boolean }>("/health"),
  summary: () => request<Summary>("/summary"),
  dashboardSummary: () => request<DashboardSummary>("/api/dashboard/summary"),
  settings: () => request<SystemSettings>("/api/settings"),
  updateSettings: (settings: Partial<SystemSettings>) => request<SystemSettings>("/api/settings", {
    method: "PATCH",
    body: JSON.stringify(settings),
  }),
  testSettings: (integration: string, draft?: Partial<SystemSettings>) => request<{ ok: boolean; message: string }>(`/api/settings/test/${integration}`, {
    method: "POST",
    body: JSON.stringify(draft ?? {}),
  }),
  currentFocus: () => request<{ current_session: FocusSession | null }>("/api/focus/current"),
  startFocus: (payload: { task_id?: number | null; project_id?: number | null; paper_id?: number | null; reading_note_id?: number | null; focus_type?: string | null; context_type?: string | null; note?: string | null }) => request<FocusSession>("/api/focus/start", {
    method: "POST",
    body: JSON.stringify(payload),
  }),
  pauseFocus: (id: number) => request<FocusSession>(`/api/focus/${id}/pause`, { method: "POST" }),
  resumeFocus: (id: number) => request<FocusSession>(`/api/focus/${id}/resume`, { method: "POST" }),
  finishFocus: (id: number) => request<FocusSession>(`/api/focus/${id}/finish`, { method: "POST" }),
  focusStats: (range: "today" | "week" | "month") => request<{ range: string; duration_seconds: number }>(`/api/focus/stats?range=${range}`),
  dashboardLayout: () => request<{ layout: any[] }>("/dashboard/layout"),
  saveDashboardLayout: (layout: any[]) => request<{ layout: any[] }>("/dashboard/layout", {
    method: "PUT",
    body: JSON.stringify({ layout }),
  }),
  directories: (path?: string) => request<DirectoryListing>(`/filesystem/directories${path ? `?path=${encodeURIComponent(path)}` : ""}`),
  projects: (params?: { search?: string; status?: string; tag?: string; sort?: string }) => {
    const query = new URLSearchParams();
    if (params?.search) query.set("search", params.search);
    if (params?.status) query.set("status", params.status);
    if (params?.tag) query.set("tag", params.tag);
    if (params?.sort) query.set("sort", params.sort);
    return request<Project[]>(`/projects${query.toString() ? `?${query.toString()}` : ""}`);
  },
  discoverProjects: () => request<any[]>("/projects/discover"),
  scanProject: (path: string) => request<ProjectScan>("/projects/scan", {
    method: "POST",
    body: JSON.stringify({ path }),
  }),
  registerProject: (payload: any) => request<Project>("/projects/register", {
    method: "POST",
    body: JSON.stringify(payload),
  }),
  createProject: (project: Partial<Project>) => request<Project>("/projects", {
    method: "POST",
    body: JSON.stringify(project),
  }),
  updateProject: (id: number, project: Partial<Project>) => request<Project>(`/projects/${id}`, {
    method: "PATCH",
    body: JSON.stringify(project),
  }),
  refreshProjectsGit: () => request<Project[]>("/projects/refresh-git", { method: "POST" }),
  projectDetail: (id: number) => request<any>(`/projects/${id}/detail`),
  projectProgress: (id: number) => request<ProjectProgress>(`/projects/${id}/progress`),
  initializeProjectProgress: (id: number) => request<any>(`/projects/${id}/progress/initialize`, { method: "POST" }),
  createStage: (stage: any) => request<any>("/project-stages", {
    method: "POST",
    body: JSON.stringify(stage),
  }),
  updateStage: (id: number, stage: any) => request<any>(`/project-stages/${id}`, {
    method: "PATCH",
    body: JSON.stringify(stage),
  }),
  gitInit: (id: number) => request<any>(`/projects/${id}/git/init`, { method: "POST" }),
  gitStatus: (id: number) => request<any>(`/projects/${id}/git/status`),
  gitDiff: (id: number, file?: string, staged?: boolean) => request<any>(`/projects/${id}/git/diff${file || staged ? `?${new URLSearchParams({ ...(file ? { file } : {}), ...(staged ? { staged: "true" } : {}) }).toString()}` : ""}`),
  gitStage: (id: number, files: string[]) => request<any>(`/projects/${id}/git/stage`, {
    method: "POST",
    body: JSON.stringify({ files }),
  }),
  gitUnstage: (id: number, files: string[]) => request<any>(`/projects/${id}/git/unstage`, {
    method: "POST",
    body: JSON.stringify({ files }),
  }),
  gitCommit: (id: number, files: string[], message: string) => request<any>(`/projects/${id}/git/commit`, {
    method: "POST",
    body: JSON.stringify({ files, message }),
  }),
  gitPush: (id: number, branch?: string) => request<any>(`/projects/${id}/git/push`, {
    method: "POST",
    body: JSON.stringify({ confirm: true, branch }),
  }),
  gitPull: (id: number, branch?: string) => request<any>(`/projects/${id}/git/pull`, {
    method: "POST",
    body: JSON.stringify({ branch }),
  }),
  prePushCheck: (id: number) => request<any>(`/projects/${id}/git/pre-push-check`),
  publishGithub: (id: number, payload: any) => request<any>(`/projects/${id}/publish-github`, {
    method: "POST",
    body: JSON.stringify(payload),
  }),
  versions: (id: number) => request<GitCommit[]>(`/projects/${id}/versions`),
  versionDetail: (id: number, hash: string) => request<any>(`/projects/${id}/versions/${hash}`),
  openVersion: (id: number, hash: string) => request<any>(`/projects/${id}/versions/${hash}/open`, { method: "POST" }),
  createBranchFromVersion: (id: number, hash: string, name: string) => request<any>(`/projects/${id}/versions/${hash}/branch`, {
    method: "POST",
    body: JSON.stringify({ name }),
  }),
  restoreVersion: (id: number, hash: string, confirm: boolean) => request<any>(`/projects/${id}/versions/${hash}/restore`, {
    method: "POST",
    body: JSON.stringify({ confirm, create_backup_branch: true }),
  }),
  tasks: () => request<Task[]>("/tasks"),
  createTask: (task: Partial<Task>) => request<Task>("/tasks", {
    method: "POST",
    body: JSON.stringify(task),
  }),
  updateTask: (id: number, payload: Partial<Task>) => request<Task>(`/tasks/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  }),
  deleteTask: (id: number) => request<{ ok: boolean }>(`/tasks/${id}`, { method: "DELETE" }),
  progressLogs: (date?: string, projectId?: number) => {
    const params = new URLSearchParams();
    if (date) params.set("date", date);
    if (projectId) params.set("project_id", String(projectId));
    const query = params.toString();
    return request<ProjectProgressLog[]>(`/project-progress${query ? `?${query}` : ""}`);
  },
  createProgressLog: (log: Partial<ProjectProgressLog>) => request<ProjectProgressLog>("/project-progress", {
    method: "POST",
    body: JSON.stringify(log),
  }),
  updateProgressLog: (id: number, payload: Partial<ProjectProgressLog>) => request<ProjectProgressLog>(`/project-progress/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  }),
  deleteProgressLog: (id: number) => request<{ ok: boolean }>(`/project-progress/${id}`, { method: "DELETE" }),
  papers: (params?: { venue?: string; status?: string; queue?: boolean }) => {
    const query = new URLSearchParams();
    if (params?.venue) query.set("venue", params.venue);
    if (params?.status) query.set("status", params.status);
    if (params?.queue) query.set("queue", "true");
    return request<Paper[]>(`/papers${query.toString() ? `?${query.toString()}` : ""}`);
  },
  savePaper: (paper: Partial<Paper>) => request<Paper>("/papers", {
    method: "POST",
    body: JSON.stringify(paper),
  }),
  saveCandidate: (paper: SearchPaper, options?: { priority?: string; reading_purpose?: string | null; related_project_id?: number | null }) => request<Paper>("/papers/candidate", {
    method: "POST",
    body: JSON.stringify({ paper, ...(options ?? {}) }),
  }),
  addToLibrary: (paper: SearchPaper, options?: { priority?: string; reading_purpose?: string | null; related_project_id?: number | null }) => request<Paper>("/papers/library", {
    method: "POST",
    body: JSON.stringify({ paper, ...(options ?? {}) }),
  }),
  addManyToLibrary: (papers: SearchPaper[], options?: { priority?: string; reading_purpose?: string | null; related_project_id?: number | null }) => request<Paper[]>("/papers/library/batch", {
    method: "POST",
    body: JSON.stringify({ papers, ...(options ?? {}) }),
  }),
  updatePaper: (id: number, payload: Partial<Paper>) => request<Paper>(`/papers/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  }),
  queuePaper: (id: number, payload: { priority?: string; reading_purpose?: string; related_project_id?: number | null; reading_mode?: string | null }) => request<Paper>(`/papers/${id}/queue`, {
    method: "POST",
    body: JSON.stringify(payload),
  }),
  addExistingPaperToZotero: (id: number) => request<Paper>(`/papers/${id}/zotero`, { method: "POST" }),
  checkPaperZotero: (id: number) => request<Paper>(`/papers/${id}/zotero/check`, { method: "POST" }),
  resolvePaperPdf: (id: number) => request<Paper>(`/papers/${id}/resolve-pdf`, { method: "POST" }),
  paperOpenLinks: (id: number) => request<{ article_url?: string | null; zotero_item_uri?: string | null; zotero_attachment_uri?: string | null }>(`/papers/${id}/open-links`),
  attachPaperPdf: (id: number, payload: { content_base64: string; filename?: string | null; content_type?: string | null; pdf_url?: string | null }) => request<Paper>(`/papers/${id}/attach-pdf`, {
    method: "POST",
    body: JSON.stringify(payload),
  }),
  syncZoteroPapers: () => request<{ status: string; synced: number; failed: Array<{ item_key: string; title: string; error: string }>; message: string }>("/zotero/sync", { method: "POST" }),
  pullFromZotero: () => request<{ status: string; imported: number; updated: number; skipped: number; total: number; message: string }>("/zotero/pull", { method: "POST" }),
  paperDetail: (id: number) => request<any>(`/papers/${id}/detail`),
  searchPapers: (payload: any) => request<{ papers: SearchPaper[] }>("/papers/search", {
    method: "POST",
    body: JSON.stringify(payload),
  }),
  importZotero: (papers: SearchPaper[]) => request<any>("/papers/import-zotero", {
    method: "POST",
    body: JSON.stringify({ collection_root: "Embodied Intelligence Papers", papers }),
  }),
  notes: (paperId?: number) => request<ReadingNote[]>(`/reading-notes${paperId ? `?paper_id=${paperId}` : ""}`),
  createNote: (note: Partial<ReadingNote>) => request<ReadingNote>("/reading-notes", {
    method: "POST",
    body: JSON.stringify(note),
  }),
  createPaperNote: (paperId: number) => request<ReadingNote>(`/papers/${paperId}/reading-note`, { method: "POST" }),
  updateNote: (id: number, payload: Partial<ReadingNote>) => request<ReadingNote>(`/reading-notes/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  }),
  exportNote: (id: number) => request<{ filename: string; content: string }>(`/reading-notes/${id}/export`),
  experiments: () => request<Experiment[]>("/experiments"),
  createExperiment: (experiment: Partial<Experiment>) => request<Experiment>("/experiments", {
    method: "POST",
    body: JSON.stringify(experiment),
  }),
  knowledge: () => request<KnowledgeLink[]>("/knowledge-links"),
  createKnowledge: (knowledge: Partial<KnowledgeLink>) => request<KnowledgeLink>("/knowledge-links", {
    method: "POST",
    body: JSON.stringify(knowledge),
  }),
  linkPaperKnowledge: (paperId: number, knowledgeId: number) => request<Paper>(`/papers/${paperId}/knowledge-links/${knowledgeId}`, { method: "PUT" }),
  unlinkPaperKnowledge: (paperId: number, knowledgeId: number) => request<Paper>(`/papers/${paperId}/knowledge-links/${knowledgeId}`, { method: "DELETE" }),
};

