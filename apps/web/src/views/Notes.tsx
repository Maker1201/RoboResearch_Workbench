import { useEffect, useState } from "react";
import { Plus } from "lucide-react";
import { api } from "../api";
import type { Paper, ReadingNote } from "../types";
import { ui } from "../i18n";

export function Notes({ t, notes, papers, refresh }: { t: typeof ui.zh.notes; notes: ReadingNote[]; papers: Paper[]; refresh: () => Promise<void> }) {
  const [paperId, setPaperId] = useState("");
  const [title, setTitle] = useState(t.defaultTitle);
  const [content, setContent] = useState(t.template);

  useEffect(() => {
    setTitle(t.defaultTitle);
    setContent(t.template);
  }, [t.defaultTitle, t.template]);

  async function create() {
    await api.createNote({ paper_id: paperId ? Number(paperId) : null, title, content, status: "draft" });
    await refresh();
  }

  return (
    <section className="notes-layout">
      <div className="panel accent-cyan note-editor-panel">
        <h2>{t.createTitle}</h2>
        <div className="form-grid">
          <input value={title} onChange={(event) => setTitle(event.target.value)} />
          <select value={paperId} onChange={(event) => setPaperId(event.target.value)}>
            <option value="">{t.noPaper}</option>
            {papers.map((paper) => <option key={paper.id} value={paper.id}>{paper.title}</option>)}
          </select>
          <textarea className="large note-template" value={content} onChange={(event) => setContent(event.target.value)} />
          <button className="primary" onClick={() => void create()}><Plus size={16} />{t.create}</button>
        </div>
      </div>
      <div className="panel accent-violet note-preview-panel">
        <h2>预览</h2>
        <pre className="note-preview">{content}</pre>
      </div>
      <div className="panel accent-amber note-list-panel">
        <h2>{t.listTitle}</h2>
        <div className="list compact-cards">{notes.map((note) => <div className="list-card" key={note.id}><strong>{note.title}</strong><span>{note.status}</span><p>{note.content.slice(0, 260)}</p></div>)}</div>
      </div>
    </section>
  );
}

