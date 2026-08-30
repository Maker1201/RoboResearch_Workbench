import { useState } from "react";
import { Link2, Plus, Unlink } from "lucide-react";
import { api } from "../api";
import type { KnowledgeLink, Paper } from "../types";
import { ui } from "../i18n";

export function Knowledge({ t, knowledge, papers, refresh }: { t: typeof ui.zh.knowledge; knowledge: KnowledgeLink[]; papers: Paper[]; refresh: () => Promise<void> }) {
  const [form, setForm] = useState({ title: "VLA Action Representation", area: "Embodied AI", obsidian_uri: "", vault_path: "EmbodiedAI/VLA/Action-Representation.md", tags: "VLA,Action Tokenization" });
  const [linkPaperId, setLinkPaperId] = useState("");
  const [linkKnowledgeId, setLinkKnowledgeId] = useState("");
  const [linkMessage, setLinkMessage] = useState("");
  async function create() {
    await api.createKnowledge(form);
    await refresh();
  }
  async function link(unlink = false) {
    const paperId = Number(linkPaperId);
    const knowledgeId = Number(linkKnowledgeId);
    if (!paperId || !knowledgeId) {
      setLinkMessage(unlink ? "请选择要解除关联的论文和知识条目。" : "请选择要关联的论文和知识条目。");
      return;
    }
    if (unlink) {
      await api.unlinkPaperKnowledge(paperId, knowledgeId);
      setLinkMessage("已解除关联。");
    } else {
      await api.linkPaperKnowledge(paperId, knowledgeId);
      setLinkMessage("已关联。可在文献详情中查看关联的知识条目。");
    }
    await refresh();
  }
  return (
    <section className="page-grid">
      <div className="panel">
        <h2>{t.newTitle}</h2>
        <div className="form-grid">
          <input value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} />
          <input value={form.area} onChange={(event) => setForm({ ...form, area: event.target.value })} />
          <input value={form.obsidian_uri} onChange={(event) => setForm({ ...form, obsidian_uri: event.target.value })} placeholder="obsidian://..." />
          <input value={form.vault_path} onChange={(event) => setForm({ ...form, vault_path: event.target.value })} />
          <input value={form.tags} onChange={(event) => setForm({ ...form, tags: event.target.value })} />
          <button className="primary" onClick={() => void create()}><Plus size={16} />{t.create}</button>
        </div>
      </div>
      <div className="panel">
        <h2>关联论文</h2>
        <div className="form-grid">
          <select value={linkPaperId} onChange={(event) => setLinkPaperId(event.target.value)}>
            <option value="">选择论文…</option>
            {papers.map((paper) => <option key={paper.id} value={paper.id}>{paper.title}</option>)}
          </select>
          <select value={linkKnowledgeId} onChange={(event) => setLinkKnowledgeId(event.target.value)}>
            <option value="">选择知识条目…</option>
            {knowledge.map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}
          </select>
          <button onClick={() => void link(false)}><Link2 size={16} />建立关联</button>
          <button onClick={() => void link(true)}><Unlink size={16} />解除关联</button>
          {linkMessage && <p className="muted">{linkMessage}</p>}
        </div>
      </div>
      <div className="panel wide">
        <h2>{t.listTitle}</h2>
        <div className="paper-grid">{knowledge.map((item) => <article className="paper-card" key={item.id}><h3>{item.title}</h3><p>{item.area}</p><p>{item.vault_path}</p>{item.obsidian_uri && <a href={item.obsidian_uri}>{t.openObsidian}</a>}</article>)}</div>
      </div>
    </section>
  );
}
