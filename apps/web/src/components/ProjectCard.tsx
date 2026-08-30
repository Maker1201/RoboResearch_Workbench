import type { Project } from "../types";
import { ProgressLine } from "./ProgressLine";
import { healthText, projectStatusText } from "../utils";

export function ProjectCard({ project, selected, onClick }: { project: Project; selected: boolean; onClick: () => void }) {
  return <button className={`project-card-row ${selected ? "selected" : ""}`} onClick={onClick}><div><strong>{project.name}</strong><span>{project.description || project.project_type || project.path}</span></div><span className={`status-pill ${project.status.toLowerCase()}`}>{projectStatusText(project.status)}</span><ProgressLine label={project.current_stage || "未设置当前阶段"} value={project.progress} /><div className="project-meta"><span>{project.path ? "本地 ✓" : "本地 -"}</span><span>{project.branch ? `Git ${project.branch}` : "Git -"}</span><span>{project.remote_url ? "GitHub ✓" : "GitHub -"}</span><span>{healthText(project.health)}</span></div></button>;
}
