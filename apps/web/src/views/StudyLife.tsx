import { useEffect, useState } from "react";
import { Plus } from "lucide-react";
import { api } from "../api";
import type { Task } from "../types";
import { ui } from "../i18n";
import { formatInputDate } from "../utils";
import { TaskItem } from "../components/TaskItem";

export function StudyLife({ t, tasks, refresh, initialDate }: { t: typeof ui.zh.study; tasks: Task[]; refresh: () => Promise<void>; initialDate?: string | null }) {
  const today = formatInputDate(new Date());
  const [activeDate, setActiveDate] = useState(initialDate || today);
  const [scheduleTitle, setScheduleTitle] = useState("");
  const [scheduleTime, setScheduleTime] = useState("");

  useEffect(() => {
    if (initialDate) setActiveDate(initialDate);
  }, [initialDate]);

  const personalTasks = tasks.filter((task) => !task.project_id);
  const todayTasks = personalTasks
    .filter((task) => (task.due_date ?? today) === activeDate)
    .sort((a, b) => (a.due_time ?? "99:99").localeCompare(b.due_time ?? "99:99"));
  async function addScheduleTask() {
    if (!scheduleTitle.trim()) return;
    await api.createTask({ title: scheduleTitle.trim(), due_date: activeDate, due_time: scheduleTime || null, priority: "medium", status: "todo" });
    setScheduleTitle("");
    setScheduleTime("");
    await refresh();
  }


  return (
    <section className="dense-grid study-layout">
      <div className="panel accent-cyan study-day-panel">
        <div className="panel-heading compact-heading study-heading">
          <h2>{t.schedule} · {activeDate}</h2>
          <input type="date" value={activeDate} onChange={(event) => setActiveDate(event.target.value || today)} title={t.schedule} />
        </div>
        <div className="form-grid inline-form task-add-form time-first">
          <input type="time" value={scheduleTime} onChange={(event) => setScheduleTime(event.target.value)} title={t.timeOptional} />
          <input value={scheduleTitle} onChange={(event) => setScheduleTitle(event.target.value)} placeholder={t.taskPlaceholder}
            onKeyDown={(event) => event.key === "Enter" && void addScheduleTask()} />
          <button className="primary" onClick={() => void addScheduleTask()}><Plus size={16} />{t.addTask}</button>
        </div>
        <div className="list compact-cards">
          {todayTasks.length
            ? todayTasks.map((task) => <TaskItem key={task.id} task={task} refresh={refresh} />)
            : <p className="muted">{t.noSchedule}</p>}
        </div>
      </div>
    </section>
  );
}
