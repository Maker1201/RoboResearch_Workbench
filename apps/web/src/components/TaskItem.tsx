import { useState } from "react";
import { Check, Circle, CircleCheck, Pencil, Trash2, X } from "lucide-react";
import { api } from "../api";
import type { Task } from "../types";
import { taskPriorityLabel, taskStatusLabel } from "../utils";
import { ui } from "../i18n";

export type TaskItemText = typeof ui.zh.common;

export function TaskItem({ task, refresh, showDate = false, readOnly = false }: {
  task: Task;
  refresh: () => Promise<void>;
  showDate?: boolean;
  readOnly?: boolean;
}) {
  const t = ui[localStorage.getItem("rrw-lang") === "en" ? "en" : "zh"].common;
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState(task.title);
  const [dueDate, setDueDate] = useState(task.due_date ?? "");
  const [dueTime, setDueTime] = useState(task.due_time ?? "");
  const [priority, setPriority] = useState(task.priority || "medium");
  const [status, setStatus] = useState(task.status || "todo");
  const [notes, setNotes] = useState(task.notes ?? "");

  async function toggle() {
    await api.updateTask(task.id, { status: task.status === "done" ? "todo" : "done" });
    await refresh();
  }

  async function save() {
    if (!title.trim()) return;
    await api.updateTask(task.id, {
      title: title.trim(),
      due_date: dueDate || null,
      due_time: dueTime || null,
      priority,
      status,
      notes: notes.trim() || null,
    });
    setEditing(false);
    await refresh();
  }

  async function remove() {
    if (!window.confirm(t.deleteConfirm)) return;
    await api.deleteTask(task.id);
    await refresh();
  }

  if (editing) {
    return (
      <div className="day-task task-editing">
        <div className="task-edit-grid">
          <input className="edit-title" value={title} onChange={(event) => setTitle(event.target.value)} placeholder={t.titlePlaceholder} autoFocus />
          <input type="date" value={dueDate} onChange={(event) => setDueDate(event.target.value)} />
          <input type="time" value={dueTime} onChange={(event) => setDueTime(event.target.value)} />
          <select value={priority} onChange={(event) => setPriority(event.target.value)}>
            <option value="high">{taskPriorityLabel("high")}</option>
            <option value="medium">{taskPriorityLabel("medium")}</option>
            <option value="low">{taskPriorityLabel("low")}</option>
          </select>
          <select value={status} onChange={(event) => setStatus(event.target.value)}>
            <option value="todo">{taskStatusLabel("todo")}</option>
            <option value="doing">{taskStatusLabel("doing")}</option>
            <option value="done">{taskStatusLabel("done")}</option>
          </select>
          <input className="edit-notes" value={notes} onChange={(event) => setNotes(event.target.value)} placeholder={t.notesPlaceholder} />
          <div className="toolbar task-edit-actions">
            <button className="primary" onClick={() => void save()}><Check size={16} />{t.save}</button>
            <button onClick={() => setEditing(false)}><X size={16} />{t.cancel}</button>
          </div>
        </div>
      </div>
    );
  }

  const timeLabel = task.due_time || (showDate && task.due_date ? task.due_date : "--:--");

  return (
    <div className={`day-task ${task.status === "done" ? "task-done" : ""} ${readOnly ? "readonly-task" : ""}`}>
      {readOnly ? (
        <span className="task-state-icon">
          {task.status === "done" ? <CircleCheck size={17} /> : <Circle size={17} />}
        </span>
      ) : (
        <button title={task.status === "done" ? t.reopen : t.markDone} onClick={() => void toggle()}>
          {task.status === "done" ? <CircleCheck size={17} /> : <Circle size={17} />}
        </button>
      )}
      <time>{timeLabel}</time>
      <div className="task-main">
        <strong>{task.title}</strong>
        <span>
          {showDate && task.due_date && task.due_time ? `${task.due_date} · ` : ""}
          {taskPriorityLabel(task.priority)} · {taskStatusLabel(task.status)}
        </span>
      </div>
      {!readOnly && (
        <>
          <button className="task-action" title={t.edit} onClick={() => setEditing(true)}><Pencil size={15} /></button>
          <button className="task-action danger" title={t.delete} onClick={() => void remove()}><Trash2 size={15} /></button>
        </>
      )}
    </div>
  );
}
