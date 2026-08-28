import type { DashboardSummary, Experiment, FocusSession, KnowledgeLink, Paper, Project, ProjectProgressLog, ReadingNote, SearchPaper, Summary, SystemSettings, Task } from "./types";

export const API_BASE = import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8765";

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
  testSettings: (integration: string) => request<{ ok: boolean; message: string }>(`/api/settings/test/${integration}`, { method: "POST" }),
  currentFocus: () => request<{ current_session: FocusSession | null }>("/api/focus/current"),
  startFocus: (payload: { task_id?: number | null; project_id?: number | null; note?: string | null }) => request<FocusSession>("/api/focus/start", {
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
  projects: () => request<Project[]>("/projects"),
  discoverProjects: () => request<any[]>("/projects/discover"),
  createProject: (project: Partial<Project>) => request<Project>("/projects", {
    method: "POST",
    body: JSON.stringify(project),
  }),
  gitStatus: (id: number) => request<any>(`/projects/${id}/git/status`),
  gitDiff: (id: number, file?: string) => request<any>(`/projects/${id}/git/diff${file ? `?file=${encodeURIComponent(file)}` : ""}`),
  gitCommit: (id: number, files: string[], message: string) => request<any>(`/projects/${id}/git/commit`, {
    method: "POST",
    body: JSON.stringify({ files, message }),
  }),
  gitPush: (id: number, branch?: string) => request<any>(`/projects/${id}/git/push`, {
    method: "POST",
    body: JSON.stringify({ confirm: true, branch }),
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
  papers: (venue?: string) => request<Paper[]>(`/papers${venue ? `?venue=${encodeURIComponent(venue)}` : ""}`),
  savePaper: (paper: Partial<Paper>) => request<Paper>("/papers", {
    method: "POST",
    body: JSON.stringify(paper),
  }),
  searchPapers: (payload: any) => request<{ papers: SearchPaper[] }>("/papers/search", {
    method: "POST",
    body: JSON.stringify(payload),
  }),
  importZotero: (papers: SearchPaper[]) => request<any>("/papers/import-zotero", {
    method: "POST",
    body: JSON.stringify({ collection_root: "Embodied Intelligence Papers", papers }),
  }),
  notes: () => request<ReadingNote[]>("/reading-notes"),
  createNote: (note: Partial<ReadingNote>) => request<ReadingNote>("/reading-notes", {
    method: "POST",
    body: JSON.stringify(note),
  }),
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
};

