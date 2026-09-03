import { useEffect, useState } from "react";
import { Link2, Pencil, Plus, Search, Sparkles, Trash2, Unlink, X } from "lucide-react";
import { api } from "../api";
import type { KnowledgeInboxItem, KnowledgeLink, Paper } from "../types";
import { ui } from "../i18n";
import { friendlyError } from "../utils";

export function Knowledge({ t, knowledge, papers, refresh }: { t: typeof ui.zh.knowledge; knowledge: KnowledgeLink[]; papers: Paper[]; refresh: () => Promise<void> }) {
  const emptyForm = { title: "", area: "", obsidian_uri: "", vault_path: "", tags: "" };
  const [form, setForm] = useState(emptyForm);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [linkPaperId, setLinkPaperId] = useState("");
  const [linkKnowledgeId, setLinkKnowledgeId] = useState("");
  const [linkMessage, setLinkMessage] = useState("");
  const [inbox, setInbox] = useState<KnowledgeInboxItem[]>([]);
  const [selectedInboxId, setSelectedInboxId] = useState<number | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [directMatches, setDirectMatches] = useState<KnowledgeLink[]>([]);
  const [related, setRelated] = useState<KnowledgeLink[]>([]);
  const [message, setMessage] = useState("");
  const [globalSearchQuery, setGlobalSearchQuery] = useState("");
  const [globalDirectMatches, setGlobalDirectMatches] = useState<KnowledgeLink[]>([]);
  const [globalRelated, setGlobalRelated] = useState<KnowledgeLink[]>([]);
  const [globalSearched, setGlobalSearched] = useState(false);
  const [globalSearchLoading, setGlobalSearchLoading] = useState(false);
  const [globalSearchFeedback, setGlobalSearchFeedback] = useState("");
  const [activeSupplementId, setActiveSupplementId] = useState<number | null>(null);
  const [supplementForm, setSupplementForm] = useState({ title: "", content: "", comment: "" });
  const [createForm, setCreateForm] = useState({ title: "", category: "Robot Task Planning", tags: "", type: "Concept", status: "seed", evidence_level: "literature", obsidian_path: "" });
  const selectedInbox = inbox.find((item) => item.id === selectedInboxId) || inbox[0];

  useEffect(() => {
    void loadInbox();
  }, []);

  useEffect(() => {
    if (selectedInbox) {
      const seed = selectedInbox.comment || selectedInbox.selected_text || selectedInbox.paper_title || "";
      setSearchQuery(seed.slice(0, 80));
      setCreateForm((current) => ({ ...current, title: suggestTitle(selectedInbox), tags: selectedInbox.tags || current.tags }));
    }
  }, [selectedInbox?.id]);

  async function loadInbox() {
    const items = await api.knowledgeInbox({ status: "pending" });
    setInbox(items);
    if (!selectedInboxId && items.length) setSelectedInboxId(items[0].id);
  }

  async function create() {
    if (editingId) {
      await api.updateKnowledge(editingId, form);
      setMessage(t.updated);
    } else {
      await api.createKnowledge(form);
      setMessage(t.created);
    }
    setForm(emptyForm);
    setEditingId(null);
    await refresh();
  }

  function editKnowledge(item: KnowledgeLink) {
    setEditingId(item.id);
    setForm({
      title: item.title || "",
      area: item.area || "",
      obsidian_uri: item.obsidian_uri || "",
      vault_path: item.vault_path || "",
      tags: item.tags || "",
    });
  }

  async function deleteKnowledge(item: KnowledgeLink) {
    if (!window.confirm(t.deleteConfirm)) return;
    await api.deleteKnowledge(item.id);
    if (editingId === item.id) {
      setEditingId(null);
      setForm(emptyForm);
    }
    setMessage(t.deleted);
    await refresh();
  }

  async function link(unlink = false) {
    const paperId = Number(linkPaperId);
    const knowledgeId = Number(linkKnowledgeId);
    if (!paperId || !knowledgeId) {
      setLinkMessage(unlink ? t.selectUnlinkTargets : t.selectLinkTargets);
      return;
    }
    if (unlink) {
      await api.unlinkPaperKnowledge(paperId, knowledgeId);
      setLinkMessage(t.unlinkedMessage);
    } else {
      await api.linkPaperKnowledge(paperId, knowledgeId);
      setLinkMessage(t.linkedMessage);
    }
    await refresh();
  }

  async function searchExisting() {
    const result = await api.searchKnowledge(searchQuery);
    setDirectMatches(result.direct_matches);
    setRelated(result.related);
  }

  async function searchGlobalKnowledge() {
    const query = globalSearchQuery.trim();
    if (!query) {
      setGlobalSearchFeedback(t.searchEmptyHint);
      setGlobalSearched(false);
      return;
    }
    setMessage("");
    setGlobalSearchLoading(true);
    setGlobalSearched(true);
    setGlobalDirectMatches([]);
    setGlobalRelated([]);
    setGlobalSearchFeedback(t.searching);
    try {
      const result = await api.searchKnowledge(query);
      const dedupedRelated = result.related.filter((item) => !result.direct_matches.some((direct) => direct.id === item.id));
      const count = result.direct_matches.length + dedupedRelated.length;
      setGlobalDirectMatches(result.direct_matches);
      setGlobalRelated(dedupedRelated);
      setGlobalSearchFeedback(count ? t.searchResultSummary.replace("{count}", String(count)) : t.noGlobalSearchResult);
    } catch (error) {
      setGlobalSearchFeedback(`${t.searchFailed}: ${friendlyError(error)}`);
    } finally {
      setGlobalSearchLoading(false);
    }
  }

  function prepareCreateFromSearch() {
    const title = globalSearchQuery.trim().slice(0, 100);
    setEditingId(null);
    setForm({ ...emptyForm, title, area: "Robot Task Planning" });
    setMessage(t.createOrRefineHint);
    window.setTimeout(() => document.getElementById("knowledge-link-form")?.scrollIntoView({ behavior: "smooth", block: "start" }), 0);
  }

  function openSupplement(item: KnowledgeLink) {
    setActiveSupplementId(item.id);
    setSupplementForm({ title: globalSearchQuery.trim() || item.title, content: "", comment: "" });
  }

  async function saveManualSupplement(item: KnowledgeLink) {
    try {
      await api.appendKnowledgeEvidence(item.id, {
        manual_title: supplementForm.title || globalSearchQuery || item.title,
        manual_content: supplementForm.content,
        manual_comment: supplementForm.comment,
        tags: item.tags || null,
      });
      setActiveSupplementId(null);
      setSupplementForm({ title: "", content: "", comment: "" });
      await refresh();
      setMessage(t.supplementSaved);
    } catch (error) {
      setMessage(`${t.actionFailed}: ${friendlyError(error)}`);
    }
  }

  async function appendEvidence(knowledgeId: number) {
    if (!selectedInbox) return;
    try {
      await api.appendKnowledgeEvidence(knowledgeId, { inbox_item_id: selectedInbox.id });
      await Promise.all([loadInbox(), refresh()]);
      setMessage(t.appended);
    } catch (error) {
      setMessage(`${t.actionFailed}: ${friendlyError(error)}`);
    }
  }

  async function createFromInbox() {
    if (!selectedInbox) return;
    try {
      await api.createKnowledgeFromInbox({
        inbox_item_id: selectedInbox.id,
        title: createForm.title,
        category: createForm.category,
        tags: createForm.tags,
        type: createForm.type,
        status: createForm.status,
        evidence_level: createForm.evidence_level,
        obsidian_path: createForm.obsidian_path || null,
        related_knowledge_ids: [],
      });
      await Promise.all([loadInbox(), refresh()]);
      setMessage(t.created);
    } catch (error) {
      setMessage(`${t.actionFailed}: ${friendlyError(error)}`);
    }
  }

  async function ignoreInbox() {
    if (!selectedInbox) return;
    await api.updateKnowledgeInbox(selectedInbox.id, { status: "ignored" });
    await loadInbox();
    setMessage(t.ignoredMessage);
  }

  function inboxTypeLabel(type: string) {
    if (type === "knowledge") return "Knowledge";
    if (type === "idea") return "Research Idea";
    if (type === "question") return "Question";
    return type;
  }

  function statusLabel(status: string) {
    if (status === "pending") return t.pending;
    if (status === "processed") return t.processed;
    if (status === "ignored") return t.ignored;
    return status;
  }

  function suggestTitle(item: KnowledgeInboxItem) {
    const text = (item.comment || item.selected_text || "").replace(/#(knowledge|idea|question)\b/gi, "").trim();
    return text.split(/[。.!?\n]/)[0]?.slice(0, 80) || item.paper_title || "New Knowledge";
  }

  function renderKnowledgeActions(items: KnowledgeLink[]) {
    if (!items.length) return <p className="muted">{t.noSearchResult}</p>;
    return <div className="paper-grid knowledge-result-grid">{items.map((item) => <article className="paper-card" key={item.id}>
      <h3>{item.title}</h3>
      <p>{item.area}</p>
      <p className="muted">{item.tags}</p>
      <div className="toolbar"><button className="primary" onClick={() => void appendEvidence(item.id)}><Sparkles size={16} />{t.appendEvidence}</button>{item.obsidian_uri && <a href={item.obsidian_uri}>{t.openObsidian}</a>}</div>
    </article>)}</div>;
  }

  function renderGlobalKnowledgeResults(items: KnowledgeLink[]) {
    if (!items.length) return <p className="muted">{t.noSearchResult}</p>;
    return <div className="paper-grid knowledge-result-grid">{items.map((item) => <article className="paper-card" key={item.id}>
      <h3>{item.title}</h3>
      <p>{item.area}</p>
      <p className="muted">{item.tags}</p>
      <div className="toolbar">
        <button className="primary" onClick={() => openSupplement(item)}><Sparkles size={16} />{t.supplement}</button>
        <button onClick={() => editKnowledge(item)}><Pencil size={16} />{t.edit}</button>
        {item.obsidian_uri && <a href={item.obsidian_uri}>{t.openObsidian}</a>}
      </div>
      {activeSupplementId === item.id && <div className="supplement-editor">
        <label><span>{t.supplementTitle}</span><input value={supplementForm.title} onChange={(event) => setSupplementForm({ ...supplementForm, title: event.target.value })} placeholder={t.supplementTitlePlaceholder} /></label>
        <label><span>{t.supplementContent}</span><textarea value={supplementForm.content} onChange={(event) => setSupplementForm({ ...supplementForm, content: event.target.value })} placeholder={t.supplementContentPlaceholder} /></label>
        <label><span>{t.supplementComment}</span><textarea value={supplementForm.comment} onChange={(event) => setSupplementForm({ ...supplementForm, comment: event.target.value })} placeholder={t.supplementCommentPlaceholder} /></label>
        <div className="toolbar"><button className="primary" disabled={!supplementForm.content.trim() && !supplementForm.comment.trim()} onClick={() => void saveManualSupplement(item)}><Plus size={16} />{t.appendEvidence}</button><button onClick={() => setActiveSupplementId(null)}><X size={16} />{t.cancel}</button></div>
      </div>}
    </article>)}</div>;
  }

  return (
    <section className="page-grid knowledge-workbench">
      <div className="panel wide knowledge-search-panel">
        <div className="panel-heading"><h2>{t.searchPanelTitle}</h2><span>{t.searchPanelIntro}</span></div>
        <div className="form-grid knowledge-search-form">
          <label className="full-field"><span>{t.searchFirst}</span><input value={globalSearchQuery} onChange={(event) => setGlobalSearchQuery(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") void searchGlobalKnowledge(); }} placeholder={t.searchPlaceholder} /></label>
          <div className="toolbar knowledge-search-actions">
            <button className="primary" disabled={globalSearchLoading} onClick={() => void searchGlobalKnowledge()}><Search size={16} />{globalSearchLoading ? t.searching : t.searchButton}</button>
            <button disabled={!globalSearchQuery.trim()} onClick={prepareCreateFromSearch}><Plus size={16} />{t.createFromSearch}</button>
          </div>
        </div>
        <p className="muted">{t.createOrRefineHint}</p>
        {globalSearchFeedback && <p className={globalSearchFeedback.includes(t.searchFailed) ? "notice error" : "notice"}>{globalSearchFeedback}</p>}
        {globalSearched && !globalSearchLoading && <>
          {(globalDirectMatches.length > 0 || globalRelated.length > 0) ? <>
            <h3>{t.directMatches}</h3>
            {renderGlobalKnowledgeResults(globalDirectMatches)}
            <h3>{t.relatedKnowledge}</h3>
            {renderGlobalKnowledgeResults(globalRelated)}
          </> : <div className="empty-action-card">
            <p>{t.noGlobalSearchResult}</p>
            <button className="primary" onClick={prepareCreateFromSearch}><Plus size={16} />{t.createFromSearch}</button>
          </div>}
        </>}
      </div>

      <div className="panel wide">
        <div className="panel-heading"><h2>{t.inbox}</h2><span>{t.searchFirst}</span></div>
        <div className="knowledge-inbox-layout">
          <div className="list compact-cards">
            {!inbox.length && <p className="muted">{t.noInbox}</p>}
            {inbox.map((item) => <button className={`list-item ${selectedInbox?.id === item.id ? "selected" : ""}`} key={item.id} onClick={() => setSelectedInboxId(item.id)}>
              <strong>{item.paper_title || t.sourcePaper}</strong>
              <span>{inboxTypeLabel(item.inbox_type)} · {statusLabel(item.status)} · {item.page_label || "-"}</span>
              <span>{(item.comment || item.selected_text || "").slice(0, 120)}</span>
            </button>)}
          </div>
          <div className="knowledge-inbox-detail">
            {selectedInbox && <>
              <div className="paper-detail-strip"><strong>{selectedInbox.paper_title}</strong><span>{t.type}：{inboxTypeLabel(selectedInbox.inbox_type)}</span><span>{selectedInbox.page_label || ""}</span></div>
              {selectedInbox.selected_text && <p className="annotation-quote"><strong>{t.highlight}</strong><br />{selectedInbox.selected_text}</p>}
              {selectedInbox.comment && <p className="annotation-comment"><strong>{t.myComment}</strong>{selectedInbox.comment}</p>}
              <div className="form-grid knowledge-search-form"><label className="full-field"><span>{t.searchFirst}</span><input value={searchQuery} onChange={(event) => setSearchQuery(event.target.value)} placeholder={t.searchPlaceholder} /></label><button className="primary" onClick={() => void searchExisting()}><Search size={16} />{t.searchFirst}</button><button onClick={() => void ignoreInbox()}><X size={16} />{t.ignore}</button></div>
              <h3>{t.directMatches}</h3>
              {renderKnowledgeActions(directMatches)}
              <h3>{t.relatedKnowledge}</h3>
              {renderKnowledgeActions(related)}
              <div className="nested-create-panel">
                <h3>{t.createNewKnowledge}</h3>
                <div className="form-grid">
                  <label><span>{t.title}</span><input value={createForm.title} onChange={(event) => setCreateForm({ ...createForm, title: event.target.value })} placeholder={t.createTitlePlaceholder} /></label>
                  <label><span>{t.category}</span><input value={createForm.category} onChange={(event) => setCreateForm({ ...createForm, category: event.target.value })} placeholder={t.createCategoryPlaceholder} /></label>
                  <label><span>{t.tags}</span><input value={createForm.tags} onChange={(event) => setCreateForm({ ...createForm, tags: event.target.value })} placeholder={t.createTagsPlaceholder} /></label>
                  <label><span>{t.knowledgeType}</span><select value={createForm.type} onChange={(event) => setCreateForm({ ...createForm, type: event.target.value })}>{["Concept", "Method", "Algorithm", "Checklist", "Debug", "Comparison", "Research Method", "Insight"].map((item) => <option key={item} value={item}>{item}</option>)}</select></label>
                  <label><span>{t.status}</span><select value={createForm.status} onChange={(event) => setCreateForm({ ...createForm, status: event.target.value })}>{["seed", "draft", "validated", "mature"].map((item) => <option key={item} value={item}>{item}</option>)}</select></label>
                  <label><span>{t.evidenceLevel}</span><select value={createForm.evidence_level} onChange={(event) => setCreateForm({ ...createForm, evidence_level: event.target.value })}>{["literature", "multi-source", "experimental", "real-robot"].map((item) => <option key={item} value={item}>{item}</option>)}</select></label>
                  <label className="full-field"><span>{t.obsidianPath}</span><input value={createForm.obsidian_path} onChange={(event) => setCreateForm({ ...createForm, obsidian_path: event.target.value })} placeholder={t.createPathPlaceholder} /></label>
                  <button className="primary" onClick={() => void createFromInbox()}><Plus size={16} />{t.createNewKnowledge}</button>
                </div>
              </div>
            </>}
          </div>
        </div>
        {message && <p className="muted">{message}</p>}
      </div>

      <div className="panel" id="knowledge-link-form">
        <h2>{editingId ? t.edit : t.newTitle}</h2>
        <div className="form-grid">
          <label><span>{t.title}</span><input value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} placeholder={t.titlePlaceholder} /></label>
          <label><span>{t.category}</span><input value={form.area} onChange={(event) => setForm({ ...form, area: event.target.value })} placeholder={t.areaPlaceholder} /></label>
          <label><span>Obsidian URI</span><input value={form.obsidian_uri} onChange={(event) => setForm({ ...form, obsidian_uri: event.target.value })} placeholder={t.obsidianUriPlaceholder} /></label>
          <label><span>{t.obsidianPath}</span><input value={form.vault_path} onChange={(event) => setForm({ ...form, vault_path: event.target.value })} placeholder={t.vaultPathPlaceholder} /></label>
          <label><span>{t.tags}</span><input value={form.tags} onChange={(event) => setForm({ ...form, tags: event.target.value })} placeholder={t.tagsPlaceholder} /></label>
          <button className="primary" disabled={!form.title.trim()} onClick={() => void create()}><Plus size={16} />{editingId ? t.update : t.create}</button>
          {editingId && <button onClick={() => { setEditingId(null); setForm(emptyForm); }}><X size={16} />{t.resetForm}</button>}
        </div>
      </div>
      <div className="panel">
        <h2>{t.linkPapers}</h2>
        <div className="form-grid">
          <select value={linkPaperId} onChange={(event) => setLinkPaperId(event.target.value)}>
            <option value="">{t.choosePaper}</option>
            {papers.map((paper) => <option key={paper.id} value={paper.id}>{paper.title}</option>)}
          </select>
          <select value={linkKnowledgeId} onChange={(event) => setLinkKnowledgeId(event.target.value)}>
            <option value="">{t.chooseKnowledge}</option>
            {knowledge.map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}
          </select>
          <button onClick={() => void link(false)}><Link2 size={16} />{t.linkSelected}</button>
          <button onClick={() => void link(true)}><Unlink size={16} />{t.unlinkSelected}</button>
          {linkMessage && <p className="muted">{linkMessage}</p>}
        </div>
      </div>
      <div className="panel wide">
        <h2>{t.listTitle}</h2>
        <div className="paper-grid">{knowledge.map((item) => <article className="paper-card" key={item.id}><h3>{item.title}</h3><p>{item.area}</p><p>{item.vault_path}</p><p className="muted">{item.tags}</p><div className="toolbar"><button onClick={() => editKnowledge(item)}><Pencil size={16} />{t.edit}</button><button className="danger" onClick={() => void deleteKnowledge(item)}><Trash2 size={16} />{t.delete}</button>{item.obsidian_uri && <a href={item.obsidian_uri}>{t.openObsidian}</a>}</div></article>)}</div>
      </div>
    </section>
  );
}
