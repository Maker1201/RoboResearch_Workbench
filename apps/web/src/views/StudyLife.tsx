import { useState } from "react";
import { Plus } from "lucide-react";
import { api } from "../api";
import type { Task } from "../types";
import { ui } from "../i18n";
import { taskPriorityLabel, taskStatusLabel } from "../utils";

export function StudyLife({ t, tasks, refresh }: { t: typeof ui.zh.study; tasks: Task[]; refresh: () => Promise<void> }) {
  const [title, setTitle] = useState("");
  const studyTasks = tasks.filter((task) => !task.project_id).slice(0, 8);

  async function addTask() {
    if (!title.trim()) return;
    await api.createTask({ title, priority: "medium", status: "todo" });
    setTitle("");
    await refresh();
  }

  return (
    <section className="dense-grid study-layout">
      <div className="panel accent-cyan">
        <h2>{t.schedule}</h2>
        <div className="timeline">
          {[t.morning, t.afternoon, t.evening, t.review].map((item) => <div key={item}><span>{item.slice(0, 5)}</span><strong>{item.slice(6)}</strong></div>)}
        </div>
      </div>
      <div className="panel accent-green">
        <h2>{t.plan}</h2>
        <div className="form-grid inline-form">
          <input value={title} onChange={(event) => setTitle(event.target.value)} placeholder={t.taskPlaceholder} />
          <button className="primary" onClick={() => void addTask()}><Plus size={16} />{t.addTask}</button>
        </div>
        <div className="list compact-cards">
          {studyTasks.map((task) => <div className="list-card" key={task.id}><strong>{task.title}</strong><span>{taskPriorityLabel(task.priority)} · {taskStatusLabel(task.status)}</span></div>)}
        </div>
      </div>
      <div className="panel accent-amber">
        <h2>{t.wellbeing}</h2>
        <div className="habit-grid">
          {t.habits.map((habit) => <span key={habit}>{habit}</span>)}
        </div>
      </div>
    </section>
  );
}

