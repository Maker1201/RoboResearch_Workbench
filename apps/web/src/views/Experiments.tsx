import { useState } from "react";
import { Plus } from "lucide-react";
import { api } from "../api";
import type { Experiment, Project } from "../types";
import { ui } from "../i18n";

export function Experiments({ t, experiments, projects, refresh }: { t: typeof ui.zh.experiments; experiments: Experiment[]; projects: Project[]; refresh: () => Promise<void> }) {
  const [form, setForm] = useState({ code: "EXP-001", title: t.defaultTitle, project_id: "", metrics: "success_rate=", result: "", conclusion: "" });
  async function create() {
    await api.createExperiment({ ...form, project_id: form.project_id ? Number(form.project_id) : null });
    await refresh();
  }
  return (
    <section className="page-grid">
      <div className="panel">
        <h2>{t.newTitle}</h2>
        <div className="form-grid">
          <input value={form.code} onChange={(event) => setForm({ ...form, code: event.target.value })} />
          <input value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} />
          <select value={form.project_id} onChange={(event) => setForm({ ...form, project_id: event.target.value })}>
            <option value="">{t.noProject}</option>
            {projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}
          </select>
          <textarea value={form.metrics} onChange={(event) => setForm({ ...form, metrics: event.target.value })} />
          <textarea value={form.result} onChange={(event) => setForm({ ...form, result: event.target.value })} placeholder={t.result} />
          <textarea value={form.conclusion} onChange={(event) => setForm({ ...form, conclusion: event.target.value })} placeholder={t.conclusion} />
          <button className="primary" onClick={() => void create()}><Plus size={16} />{t.create}</button>
        </div>
      </div>
      <div className="panel wide">
        <h2>{t.log}</h2>
        <div className="table">
          {experiments.map((experiment) => <div className="row" key={experiment.id}><strong>{experiment.code}</strong><span>{experiment.title}</span><span>{experiment.metrics}</span><span>{experiment.conclusion}</span></div>)}
        </div>
      </div>
    </section>
  );
}

