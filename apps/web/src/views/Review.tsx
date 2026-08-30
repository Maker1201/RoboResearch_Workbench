import type { Experiment, Paper, Project, Summary } from "../types";
import { ui } from "../i18n";
import { Metric } from "../components/Metric";

export function Review({ t, moduleRows, summary, projects, papers, experiments }: {
  t: typeof ui.zh.review;
  moduleRows: Array<{ key: string; manages: string; content: string; status: string }>;
  summary: Summary | null;
  projects: Project[];
  papers: Paper[];
  experiments: Experiment[];
}) {
  return (
    <section className="dense-grid review-layout">
      <div className="panel wide accent-cyan">
        <h2>{t.moduleAudit}</h2>
        <div className="module-table">
          {moduleRows.map((row) => <div key={row.key}><strong>{row.key}</strong><span>{row.manages}</span><em>{row.content}</em><b>{row.status === "covered" ? "已覆盖" : "待补充"}</b></div>)}
        </div>
      </div>
      <div className="panel accent-green">
        <h2>{t.weekly}</h2>
        <div className="metric-row"><Metric label={t.progress} value={summary?.active_projects ?? 0} /><Metric label={t.reading} value={summary?.papers ?? 0} /></div>
        <div className="metric-row"><Metric label={t.experiments} value={summary?.experiments ?? 0} /><Metric label={t.next} value={projects.filter((project) => project.progress < 100).length} /></div>
      </div>
      <div className="panel accent-rose">
        <h2>{t.monthly}</h2>
        <div className="review-list">
          <span>{t.reading}: {papers.length}</span>
          <span>{t.experiments}: {experiments.length}</span>
          <span>{t.progress}: {Math.round(projects.reduce((sum, item) => sum + item.progress, 0) / Math.max(projects.length, 1))}%</span>
        </div>
      </div>
      <div className="panel accent-amber">
        <h2>{t.semester}</h2>
        <textarea readOnly value={`${t.progress}\n\n${t.reading}\n\n${t.experiments}\n\n${t.next}`} />
      </div>
    </section>
  );
}

