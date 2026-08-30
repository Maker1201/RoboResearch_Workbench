import { useEffect, useState } from "react";
import { CalendarDays, Check, ChevronLeft, ChevronRight, Circle, CircleCheck, Pause, Play, Timer, X } from "lucide-react";
import { api } from "../api";
import type { DashboardSummary, FocusSession, Project, Task } from "../types";
import type { Tab } from "../constants";
import { ui } from "../i18n";
import { Metric } from "../components/Metric";
import { ProgressLine } from "../components/ProgressLine";
import { formatDisplayDate, formatInputDate, formatDuration, getMonthDays, shiftMonth, statusLabel, zhWeekdayLabels, enWeekdayLabels } from "../utils";

export function Dashboard({ t, summary, tasks, refresh, openFocus, setTab }: {
  t: typeof ui.zh.dashboard;
  summary: DashboardSummary | null;
  tasks: Task[];
  refresh: () => Promise<void>;
  openFocus: () => void;
  setTab: (tab: Tab) => void;
}) {
  const today = formatInputDate(new Date());
  const [clock, setClock] = useState(new Date());
  const [calendarDate, setCalendarDate] = useState(today);
  const [taskViewDate, setTaskViewDate] = useState<string | null>(null);

  useEffect(() => {
    const timer = window.setInterval(() => setClock(new Date()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  const visibleDate = taskViewDate ?? calendarDate;
  const selectedTasks = visibleDate === (summary?.today.date ?? today)
    ? summary?.today.tasks ?? []
    : tasks.filter((task) => task.due_date === visibleDate);
  const doneCount = selectedTasks.filter((task) => task.status === "done").length;
  const completionRate = selectedTasks.length ? Math.round((doneCount / selectedTasks.length) * 100) : 0;
  const monthDays = getMonthDays(calendarDate);
  const calendarWeekdays = t.today === "今日" ? zhWeekdayLabels : enWeekdayLabels;
  const focus = summary?.focus;
  const focusSession = focus?.current_session;
  const weekDone = summary?.today.completed_tasks ?? 0;
  const weekTotal = Math.max(summary?.today.total_tasks ?? 0, 1);
  const weekRate = Math.round((weekDone / weekTotal) * 100);

  async function toggleTask(task: Task) {
    await api.updateTask(task.id, { status: task.status === "done" ? "todo" : "done" });
    await refresh();
  }

  return (
    <section className="dashboard-readonly-grid compact-overview">
      <div className="dashboard-hero panel">
        <div className="hero-copy">
          <span>{formatDisplayDate(clock, t.today === "今日" ? "zh" : "en")} · {clock.toLocaleTimeString("zh-CN", { hour12: false })}</span>
          <h2>{t.motto}</h2>
        </div>
        <div className="hero-metrics">
          <Metric label={t.weekExecution} value={`${weekRate}%`} />
          <Metric label={t.doneTasks} value={`${summary?.today.completed_tasks ?? 0}/${summary?.today.total_tasks ?? 0}`} />
          <Metric label={t.todayDone} value={`${doneCount}/${selectedTasks.length}`} />
          <Metric label={t.focusStreak} value={formatDuration(focus?.today_duration ?? 0)} />
        </div>
      </div>

      <div className="dashboard-module-tabs panel">
        {[t.today, t.projects, t.literature, t.experiments, t.knowledge].map((item) => <span key={item}>{item}</span>)}
      </div>

      <div className="panel day-switch-card accent-cyan">
        {!taskViewDate ? (
          <>
            <div className="panel-heading compact-heading">
              <div>
                <h2>{t.calendar}</h2>
                <p>{calendarDate.slice(0, 7)}</p>
              </div>
              <div className="toolbar tight-toolbar">
                <button title={t.previousMonth} onClick={() => setCalendarDate(shiftMonth(calendarDate, -1))}><ChevronLeft size={16} /></button>
                <button title={t.nextMonth} onClick={() => setCalendarDate(shiftMonth(calendarDate, 1))}><ChevronRight size={16} /></button>
              </div>
            </div>
            <div className="calendar-weekdays compact-calendar-weekdays">{calendarWeekdays.map((day) => <span key={day}>{day}</span>)}</div>
            <div className="calendar-grid compact-calendar-grid">
              {monthDays.map((day) => {
                const dayTasks = tasks.filter((task) => (task.due_date || today) === day.date);
                return (
                  <button
                    key={day.key}
                    className={`calendar-day ${day.inMonth ? "" : "muted-day"} ${day.date === today ? "today-day" : ""}`}
                    title={t.openDayTasks}
                    onClick={() => {
                      setCalendarDate(day.date);
                      setTaskViewDate(day.date);
                    }}
                  >
                    <span>{day.day}</span>
                    {dayTasks.length > 0 && <b>{dayTasks.length}</b>}
                  </button>
                );
              })}
            </div>
          </>
        ) : (
          <>
            <div className="panel-heading compact-heading">
              <div>
                <h2>{t.dailyTasks}</h2>
                <p>{taskViewDate}</p>
              </div>
              <button onClick={() => setTaskViewDate(null)}><CalendarDays size={16} />{t.backToCalendar}</button>
            </div>
            <div className="metric-row triple compact-metrics">
              <Metric label={t.tasks} value={selectedTasks.length} />
              <Metric label={t.completed} value={doneCount} />
              <Metric label={t.completionRate} value={`${completionRate}%`} />
            </div>
            <ProgressLine label={t.completionRate} value={completionRate} />
            <div className="day-task-list module-scroll compact-day-list">
              {selectedTasks.length ? selectedTasks.map((task) => (
                <div className={`day-task readonly-task ${task.status === "done" ? "task-done" : ""}`} key={task.id}>
                  <button title={task.status === "done" ? t.reopen : t.markDone} onClick={() => void toggleTask(task)}>
                    {task.status === "done" ? <CircleCheck size={17} /> : <Circle size={17} />}
                  </button>
                  <div>
                    <strong>{task.title}</strong>
                    <span>{task.priority} · {task.status}</span>
                  </div>
                </div>
              )) : <p className="muted">{t.noTasks}</p>}
            </div>
            <button className="module-link" onClick={() => setTab("study")}>{t.viewModule}</button>
          </>
        )}
      </div>

      <div className="panel accent-violet dashboard-card focus-summary-card">
        <div className="panel-heading compact-heading">
          <h2>{t.focus}</h2>
          <button onClick={openFocus}><Timer size={16} />{t.enterFocus}</button>
        </div>
        <div className="metric-row compact-metrics">
          <Metric label={focusSession ? (focusSession.status === "PAUSED" ? t.focusPaused : t.focusRunning) : t.focusIdle} value={focusSession ? formatDuration(focusSession.elapsed_seconds) : "--"} />
          <Metric label={t.weekFocus} value={formatDuration(focus?.week_duration ?? 0)} />
        </div>
        {focusSession && <div className="record"><strong>{focusSession.task_title || focusSession.project_name || t.noItems}</strong><span>{focusSession.project_name}</span></div>}
      </div>

      <DashboardProjects t={t} summary={summary} setTab={setTab} />
      <DashboardPapers t={t} summary={summary} setTab={setTab} />
      <DashboardExperiments t={t} summary={summary} setTab={setTab} />
      <DashboardKnowledge t={t} summary={summary} setTab={setTab} />
    </section>
  );
}

function DashboardProjects({ t, summary, setTab }: { t: typeof ui.zh.dashboard; summary: DashboardSummary | null; setTab: (tab: Tab) => void }) {
  const counts = summary?.projects.counts ?? {};
  return <div className="panel dashboard-card accent-green" onDoubleClick={() => setTab("projects")}>
    <div className="panel-heading compact-heading"><h2>{t.projects}</h2><button onClick={() => setTab("projects")}>{t.viewModule}</button></div>
    <div className="metric-row triple">
      <Metric label={t.total} value={summary?.projects.total ?? 0} />
      <Metric label={t.active} value={counts.active ?? 0} />
      <Metric label={t.blocked} value={counts.blocked ?? 0} />
    </div>
    <div className="status-strip">
      {(["planning", "paused", "completed", "archived"] as const).map((key) => <span key={key}>{statusLabel(t, key)}: {counts[key] ?? 0}</span>)}
    </div>
    <div className="list module-scroll">
      {(summary?.projects.featured ?? []).map((project) => <button className="list-item" key={project.id} onClick={() => setTab("projects")}><strong>{project.name}</strong><span>{statusLabel(t, project.status)} · {Math.round(project.progress)}%</span><em>{project.current_milestone || t.currentMilestone} / {project.next_milestone || t.nextMilestone}</em></button>)}
    </div>
  </div>;
}

function DashboardPapers({ t, summary, setTab }: { t: typeof ui.zh.dashboard; summary: DashboardSummary | null; setTab: (tab: Tab) => void }) {
  const counts = summary?.papers.status_counts ?? {};
  return <div className="panel dashboard-card accent-rose">
    <div className="panel-heading compact-heading"><h2>{t.literature}</h2><button onClick={() => setTab("papers")}>{t.viewModule}</button></div>
    <div className="metric-row triple">
      <Metric label={t.inbox} value={counts.inbox ?? 0} />
      <Metric label={t.toRead} value={counts.to_read ?? 0} />
      <Metric label={t.reading} value={counts.reading ?? 0} />
    </div>
    <div className="tag-cloud dashboard-tags">{Object.entries(summary?.papers.venue_counts ?? {}).map(([venue, count]) => <span key={venue}>{venue}: {count}</span>)}</div>
    <h3>{t.currentlyReading}</h3>
    <div className="list module-scroll">{(summary?.papers.currently_reading ?? []).slice(0, 3).map((paper) => <button className="list-item" key={paper.id} onClick={() => setTab("papers")}><strong>{paper.title}</strong><span>{paper.venue} · {paper.year ?? ""}</span></button>)}</div>
  </div>;
}

function DashboardExperiments({ t, summary, setTab }: { t: typeof ui.zh.dashboard; summary: DashboardSummary | null; setTab: (tab: Tab) => void }) {
  const counts = summary?.experiments.counts ?? {};
  return <div className="panel dashboard-card accent-amber">
    <div className="panel-heading compact-heading"><h2>{t.experiments}</h2><button onClick={() => setTab("experiments")}>{t.viewModule}</button></div>
    <div className="metric-row triple">
      <Metric label={t.running} value={counts.running ?? 0} />
      <Metric label={t.pending} value={counts.pending ?? 0} />
      <Metric label={t.completed} value={counts.completed ?? 0} />
    </div>
    <Metric label={t.researchIdeas} value={summary?.experiments.research_ideas_pending ?? 0} />
    <div className="list module-scroll">{((summary?.experiments.running.length ?? 0) > 0 ? summary?.experiments.running ?? [] : summary?.experiments.recent_results ?? []).slice(0, 4).map((experiment) => <button className="list-item" key={experiment.id} onClick={() => setTab("experiments")}><strong>{experiment.code}</strong><span>{experiment.title}</span></button>)}</div>
  </div>;
}

function DashboardKnowledge({ t, summary, setTab }: { t: typeof ui.zh.dashboard; summary: DashboardSummary | null; setTab: (tab: Tab) => void }) {
  return <div className="panel dashboard-card accent-cyan">
    <div className="panel-heading compact-heading"><h2>{t.knowledge}</h2><button onClick={() => setTab("knowledge")}>{t.viewModule}</button></div>
    <div className="metric-row">
      <Metric label={summary?.knowledge.obsidian_connected ? t.obsidianConnected : t.obsidianDisconnected} value={summary?.knowledge.obsidian_connected ? "OK" : "--"} />
      <Metric label={t.totalNotes} value={summary?.knowledge.total_notes ?? 0} />
    </div>
    <Metric label={t.updatedThisWeek} value={summary?.knowledge.updated_this_week ?? 0} />
    <div className="list module-scroll">{(summary?.knowledge.recently_updated ?? []).map((item) => <button className="list-item" key={item.id} onClick={() => setTab("knowledge")}><strong>{item.title}</strong><span>{item.area}</span></button>)}</div>
  </div>;
}



export function FocusMode({ t, tasks, projects, summary, refresh, exit }: {
  t: typeof ui.zh.focusMode;
  tasks: Task[];
  projects: Project[];
  summary: DashboardSummary | null;
  refresh: () => Promise<void>;
  exit: () => void;
}) {
  const [clock, setClock] = useState(new Date());
  const [current, setCurrent] = useState<FocusSession | null>(summary?.focus.current_session ?? null);
  const [taskId, setTaskId] = useState("");
  const [projectId, setProjectId] = useState("");
  const [note, setNote] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    const timer = window.setInterval(() => {
      setClock(new Date());
      setCurrent((session) => session && session.status === "RUNNING" ? { ...session, elapsed_seconds: session.elapsed_seconds + 1 } : session);
    }, 1000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    void api.currentFocus().then((data) => setCurrent(data.current_session));
  }, []);

  async function start() {
    const session = await api.startFocus({
      task_id: taskId ? Number(taskId) : null,
      project_id: projectId ? Number(projectId) : null,
      note: note.trim() || null,
    });
    setCurrent(session);
    await refresh();
  }

  async function pause() {
    if (!current) return;
    setCurrent(await api.pauseFocus(current.id));
    await refresh();
  }

  async function resume() {
    if (!current) return;
    setCurrent(await api.resumeFocus(current.id));
    await refresh();
  }

  async function finish() {
    if (!current) return;
    setCurrent(await api.finishFocus(current.id));
    setMessage(t.finish);
    await refresh();
    const data = await api.currentFocus();
    setCurrent(data.current_session);
  }

  const todayDuration = summary?.focus.today_duration ?? 0;
  const weekDuration = summary?.focus.week_duration ?? 0;

  return (
    <section className="focus-mode-shell">
      <button className="focus-exit" onClick={exit}><X size={16} />{t.exit}</button>
      <div className="focus-clock-label">{t.currentTime}</div>
      <div className="focus-clock">{clock.toLocaleTimeString("zh-CN", { hour12: false })}</div>
      <div className="focus-timer">{formatDuration(current?.elapsed_seconds ?? 0)}</div>
      {current ? (
        <div className="focus-current">
          <strong>{current.status === "PAUSED" ? t.paused : t.running}</strong>
          <span>{current.task_title || current.project_name || current.note || t.noAssociation}</span>
          {current.project_name && <span>{current.project_name}</span>}
          <div className="toolbar focus-actions">
            {current.status === "PAUSED" ? <button className="primary" onClick={() => void resume()}><Play size={16} />{t.resume}</button> : <button onClick={() => void pause()}><Pause size={16} />{t.pause}</button>}
            <button onClick={() => void finish()}><Check size={16} />{t.finish}</button>
          </div>
        </div>
      ) : (
        <div className="panel focus-start-panel">
          <h2>{t.title}</h2>
          <div className="form-grid">
            <select value={taskId} onChange={(event) => setTaskId(event.target.value)}>
              <option value="">{t.noTask}</option>
              {tasks.map((task) => <option key={task.id} value={task.id}>{task.title}</option>)}
            </select>
            <select value={projectId} onChange={(event) => setProjectId(event.target.value)}>
              <option value="">{t.noProject}</option>
              {projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}
            </select>
            <input value={note} onChange={(event) => setNote(event.target.value)} placeholder={t.note} />
            <button className="primary" onClick={() => void start()}><Play size={16} />{t.start}</button>
          </div>
        </div>
      )}
      <div className="focus-stats">
        <Metric label={t.today} value={formatDuration(todayDuration)} />
        <Metric label={t.week} value={formatDuration(weekDuration)} />
      </div>
      {message && <p className="notice">{message}</p>}
    </section>
  );
}

