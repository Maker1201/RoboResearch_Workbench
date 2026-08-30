import type { Experiment, Paper, Project, ReadingNote } from "../types";
import { ui } from "../i18n";
import { Metric } from "../components/Metric";

export function ResearchWriting({ t, projects, papers, notes, experiments }: {
  t: typeof ui.zh.research;
  projects: Project[];
  papers: Paper[];
  notes: ReadingNote[];
  experiments: Experiment[];
}) {
  const pipeline = [t.ideas, "研究假设", "基线实验", t.figures, t.relatedWork, t.draft, t.revision, t.submission];
  return (
    <section className="dense-grid research-layout">
      <div className="panel wide accent-violet">
        <h2>{t.pipeline}</h2>
        <div className="pipeline">
          {pipeline.map((item, index) => <div key={item}><span>{String(index + 1).padStart(2, "0")}</span><strong>{item}</strong></div>)}
        </div>
      </div>
      <div className="panel accent-rose">
        <h2>{t.ideas}</h2>
        <ul className="compact-list">{t.ideaItems.map((item) => <li key={item}>{item}</li>)}</ul>
      </div>
      <div className="panel accent-amber">
        <h2>{t.figures}</h2>
        <ul className="compact-list">{t.figureItems.map((item) => <li key={item}>{item}</li>)}</ul>
      </div>
      <div className="panel accent-green">
        <h2>{t.writingBoard}</h2>
        <div className="metric-row triple">
          <Metric label="项目" value={projects.length} />
          <Metric label="文献" value={papers.length} />
          <Metric label="笔记" value={notes.length} />
        </div>
        <div className="metric-row triple">
          <Metric label="实验" value={experiments.length} />
          <Metric label={t.relatedWork} value={papers.filter((paper) => paper.status !== "inbox").length} />
          <Metric label={t.figures} value={t.figureItems.length} />
        </div>
      </div>
    </section>
  );
}

