import { useEffect, useState, type ReactNode } from "react";
import { BookOpen, Check, Clock3, Eye, Link, NotebookPen, Plus, RefreshCw, Save, Search, Send, Timer, UploadCloud, X } from "lucide-react";
import { api } from "../api";
import type { Paper, Project, ReadingNote, SearchPaper } from "../types";
import { ui } from "../i18n";
import { venues, defaultSources, readingStatuses, readingModes, readingPurposes, paperPriorities, literatureSections, literatureSectionLabels, topicFilters } from "../constants";
import { fileStartsWithPdf, friendlyError, fileToBase64, normalizePaperStatus, paperStatusLabel, pdfAssistTitle, pdfSourceLabel, priorityLabel, readingModeLabel, readingPurposeLabel, resultKey, zoteroSyncLabel } from "../utils";

export function Papers({ t, papers, projects, notes, refresh, setMessage, setLoading }: {
  t: typeof ui.zh.papers;
  papers: Paper[];
  projects: Project[];
  notes: ReadingNote[];
  refresh: () => Promise<void>;
  setMessage: (message: string) => void;
  setLoading: (value: boolean) => void;
}) {
  const [section, setSection] = useState("Search");
  const [venue, setVenue] = useState("");
  const [topic, setTopic] = useState("");
  const [query, setQuery] = useState("embodied intelligence robot task planning world model");
  const [keywords, setKeywords] = useState("VLA\nVLM\nworld model\nrobot task planning\nmanipulation");
  const [fromYear, setFromYear] = useState("2020");
  const [toYear, setToYear] = useState(String(new Date().getFullYear()));
  const [sort, setSort] = useState("relevance");
  const [results, setResults] = useState<SearchPaper[]>([]);
  const [ignored, setIgnored] = useState<Record<string, boolean>>({});
  const [selectedResults, setSelectedResults] = useState<Record<string, SearchPaper>>({});
  const [selectedPaperId, setSelectedPaperId] = useState<number | null>(null);
  const [selectedNoteId, setSelectedNoteId] = useState<number | null>(null);
  const [noteDraft, setNoteDraft] = useState("");
  const [noteSummary, setNoteSummary] = useState("");
  const [noteRelevance, setNoteRelevance] = useState("");
  const [queueForm, setQueueForm] = useState({ priority: "normal", reading_purpose: "General Interest", related_project_id: "", reading_mode: "SKIM" });

  const visibleResults = results
    .filter((paper) => !ignored[resultKey(paper)])
    .sort((a, b) => sort === "newest" ? (b.year || 0) - (a.year || 0) : b.relevance - a.relevance);
  const selectedResultList = Object.values(selectedResults);
  const candidates = papers.filter((paper) => normalizePaperStatus(paper.status) === "Candidate");
  const library = papers.filter((paper) => !["Candidate", "Dropped"].includes(normalizePaperStatus(paper.status)) && (paper.zotero_item_key || paper.zotero_key || normalizePaperStatus(paper.status) !== "Inbox"));
  const queue = papers.filter((paper) => Boolean(paper.queued_at) || ["To Read", "Skimming", "Reading", "Deep Reading"].includes(normalizePaperStatus(paper.status)));
  const filteredLibrary = library.filter((paper) => (!venue || paper.venue === venue) && (!topic || (paper.tags || "").toLowerCase().includes(topic.toLowerCase())));
  const selectedPaper = papers.find((paper) => paper.id === selectedPaperId) || queue[0] || library[0] || candidates[0];
  const selectedNotes = selectedPaper ? notes.filter((note) => note.paper_id === selectedPaper.id) : [];
  const selectedNote = notes.find((note) => note.id === selectedNoteId) || selectedNotes[0];
  useEffect(() => {
    if (selectedNote) {
      setSelectedNoteId(selectedNote.id);
      setNoteDraft(selectedNote.content_markdown || selectedNote.content || "");
      setNoteSummary(selectedNote.one_sentence_summary || "");
      setNoteRelevance(selectedNote.relevance_to_me || "");
    } else {
      setSelectedNoteId(null);
      setNoteDraft("");
      setNoteSummary("");
      setNoteRelevance("");
    }
  }, [selectedNote?.id]);

  async function search() {
    setLoading(true);
    try {
      const sources = venue ? defaultSources.filter((source) => source.label === venue) : defaultSources;
      const data = await api.searchPapers({
        query,
        sources,
        keywords: keywords.split(/\n|,/).map((item) => item.trim()).filter(Boolean),
        from_year: Number(fromYear) || 2020,
        to_year: Number(toYear) || new Date().getFullYear(),
        per_source_limit: 20,
      });
      setResults(data.papers);
      setSelectedResults({});
      setSection("Search");
      setMessage(`${t.found} ${data.papers.length} ${t.foundSuffix}`);
    } catch (error) {
      setMessage(`${t.failed}: ${friendlyError(error)}`);
    } finally {
      setLoading(false);
    }
  }

  function toggleResultSelection(paper: SearchPaper, checked: boolean) {
    const key = resultKey(paper);
    setSelectedResults((items) => {
      const next = { ...items };
      if (checked) next[key] = paper;
      else delete next[key];
      return next;
    });
  }

  function selectVisibleResults() {
    setSelectedResults((items) => {
      const next = { ...items };
      for (const paper of visibleResults) next[resultKey(paper)] = paper;
      return next;
    });
  }

  async function saveSelectedCandidates() {
    if (!selectedResultList.length) return;
    setLoading(true);
    let saved = 0;
    const failures: string[] = [];
    try {
      for (const paper of selectedResultList) {
        try {
          await api.saveCandidate(paper, { priority: queueForm.priority });
          saved += 1;
        } catch {
          failures.push(paper.title);
        }
      }
      setSelectedResults({});
      setSection("Candidates");
      await refresh();
      setMessage(failures.length ? `已保存 ${saved} 篇候选文献，${failures.length} 篇失败。` : `已保存 ${saved} 篇候选文献。`);
    } finally {
      setLoading(false);
    }
  }

  async function addSelectedToLibrary() {
    if (!selectedResultList.length) return;
    setLoading(true);
    try {
      const saved = await api.addManyToLibrary(selectedResultList, {
        priority: queueForm.priority,
        reading_purpose: queueForm.reading_purpose,
        related_project_id: queueForm.related_project_id ? Number(queueForm.related_project_id) : null,
      });
      const attached = saved.filter((paper) => paper.zotero_pdf_attached).length;
      const pending = saved.length - attached;
      setSelectedResults({});
      setSection("Library");
      await refresh();
      setMessage(`已加入 Zotero 和文献库：${saved.length} 篇。PDF 已挂载 ${attached} 篇，待补充 ${pending} 篇。`);
    } catch (error) {
      await refresh();
      setMessage(`批量加入 Zotero 失败：${friendlyError(error)}`);
    } finally {
      setLoading(false);
    }
  }

  async function saveCandidate(paper: SearchPaper) {
    const saved = await api.saveCandidate(paper, { priority: queueForm.priority });
    setSelectedPaperId(saved.id);
    setSection("Candidates");
    await refresh();
    setMessage("已保存为候选文献。");
  }

  async function addResultToLibrary(paper: SearchPaper) {
    setLoading(true);
    try {
      const saved = await api.addToLibrary(paper, {
        priority: queueForm.priority,
        reading_purpose: queueForm.reading_purpose,
        related_project_id: queueForm.related_project_id ? Number(queueForm.related_project_id) : null,
      });
      setSelectedPaperId(saved.id);
      setSection("Library");
      await refresh();
      setMessage("已添加到 Zotero 和工作台文献库。");
    } catch (error) {
      setMessage(`Zotero 导入失败：${friendlyError(error)}`);
    } finally {
      setLoading(false);
    }
  }

  async function queuePaper(paper: Paper) {
    const queued = await api.queuePaper(paper.id, {
      priority: queueForm.priority,
      reading_purpose: queueForm.reading_purpose,
      related_project_id: queueForm.related_project_id ? Number(queueForm.related_project_id) : null,
      reading_mode: queueForm.reading_mode,
    });
    setSelectedPaperId(queued.id);
    setSection("Reading Queue");
    await refresh();
    setMessage("已加入阅读队列。");
  }

  async function updatePaperStatus(paper: Paper, status: string) {
    await api.updatePaper(paper.id, { status });
    await refresh();
  }

  async function updatePaperMode(paper: Paper, reading_mode: string) {
    await api.updatePaper(paper.id, { reading_mode });
    await refresh();
  }

  async function createNote(paper: Paper) {
    const note = await api.createPaperNote(paper.id);
    setSelectedPaperId(paper.id);
    setSelectedNoteId(note.id);
    setSection("Reading Notes");
    await refresh();
  }

  async function saveNote() {
    if (!selectedNote) return;
    await api.updateNote(selectedNote.id, {
      content_markdown: noteDraft,
      one_sentence_summary: noteSummary,
      relevance_to_me: noteRelevance,
      reading_mode: selectedPaper?.reading_mode || selectedNote.reading_mode,
      reading_status_snapshot: selectedPaper?.status || selectedNote.reading_status_snapshot,
    });
    await refresh();
    setMessage("阅读笔记已保存。");
  }

  async function exportNote() {
    if (!selectedNote) return;
    const exported = await api.exportNote(selectedNote.id);
    const blob = new Blob([exported.content], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = exported.filename;
    link.click();
    URL.revokeObjectURL(url);
  }

  async function attachPdfFile(paper: Paper, file: File | null) {
    if (!file) return;
    if (file.type && file.type !== "application/pdf" && !file.name.toLowerCase().endsWith(".pdf")) {
      setMessage("请选择 PDF 文件。");
      return;
    }
    if (file.size > 80 * 1024 * 1024) {
      setMessage("PDF 文件超过 80MB，暂不自动挂载。");
      return;
    }
    setLoading(true);
    try {
      if (!(await fileStartsWithPdf(file))) {
        setMessage("请选择真实 PDF 文件，当前文件没有 PDF 文件头。");
        return;
      }
      const content = await fileToBase64(file);
      const saved = await api.attachPaperPdf(paper.id, {
        content_base64: content,
        filename: file.name || `${paper.title}.pdf`,
        content_type: file.type || "application/pdf",
        pdf_url: paper.pdf_url || paper.url || null,
      });
      setSelectedPaperId(saved.id);
      await refresh();
      setMessage("PDF 已挂载到 Zotero，并已同步工作台状态。");
    } catch (error) {
      setMessage(`PDF 无法挂载到 Zotero：${friendlyError(error)}`);
    } finally {
      setLoading(false);
    }
  }

  async function startReadingFocus() {
    if (!selectedPaper) return;
    const note = selectedNote || await api.createPaperNote(selectedPaper.id);
    await api.startFocus({ paper_id: selectedPaper.id, reading_note_id: note.id, context_type: "PAPER_READING", focus_type: "PAPER_READING", note: `阅读：${selectedPaper.title}` });
    setMessage("已从该文献开始阅读专注。");
    await refresh();
  }

  async function syncZotero() {
    setLoading(true);
    try {
      const result = await api.syncZoteroPapers();
      await refresh();
      setMessage(result.failed.length ? `${result.message} ${result.failed.length} 篇同步失败。` : result.message);
    } catch (error) {
      setMessage(`Zotero 同步失败：${friendlyError(error)}`);
    } finally {
      setLoading(false);
    }
  }


  async function checkZoteroForPaper(paper: Paper) {
    setLoading(true);
    try {
      const saved = await api.checkPaperZotero(paper.id);
      setSelectedPaperId(saved.id);
      await refresh();
      setMessage(saved.zotero_pdf_attached ? "已从 Zotero 检测到 PDF 附件。" : "Zotero 条目中暂未发现 PDF 附件。");
    } catch (error) {
      setMessage(`从 Zotero 检查 PDF 失败：${friendlyError(error)}`);
    } finally {
      setLoading(false);
    }
  }

  function paperArticleUrl(paper: Paper) {
    return paper.url || paper.source_url || (paper.doi ? `https://doi.org/${paper.doi}` : null);
  }

  function zoteroItemUri(paper: Paper) {
    const key = paper.zotero_item_key || paper.zotero_key;
    return key ? `zotero://select/library/items/${key}` : null;
  }

  function zoteroAttachmentUri(paper: Paper) {
    return paper.zotero_attachment_key ? `zotero://select/library/items/${paper.zotero_attachment_key}` : null;
  }

  function pdfNeedsAssistance(paper: Paper) {
    const status = (paper.pdf_status || paper.zotero_pdf_status || "").toUpperCase();
    return Boolean(paper.zotero_item_key || paper.zotero_key) && !paper.zotero_pdf_attached && ["BROWSER_REQUIRED", "AUTH_REQUIRED", "FAILED", "NONE"].includes(status);
  }

  function renderPdfAssist(paper: Paper) {
    if (!pdfNeedsAssistance(paper)) return null;
    const articleUrl = paperArticleUrl(paper);
    return <div className="pdf-assist-box">
      <strong>{pdfAssistTitle(paper)}</strong>
      <span>{paper.pdf_error_message || "PDF 无法自动获取。该出版社可能需要浏览器登录状态、机构权限或 Zotero Connector。"}</span>
      <div className="toolbar pdf-assist-actions">
        {articleUrl && <a href={articleUrl} target="_blank"><Link size={16} />在浏览器打开</a>}
        <button onClick={() => void checkZoteroForPaper(paper)}><RefreshCw size={16} />从 Zotero 检查 PDF</button>
        <label className="file-action-button"><UploadCloud size={16} />选择本地 PDF<input type="file" accept="application/pdf,.pdf" onChange={(event) => void attachPdfFile(paper, event.currentTarget.files?.[0] || null)} /></label>
      </div>
    </div>;
  }

  function renderPaperRow(paper: Paper, actions: ReactNode, className = "") {
    return <article className={`paper-card paper-workflow-card ${className} ${selectedPaper?.id === paper.id ? "selected" : ""}`} key={paper.id} onClick={() => setSelectedPaperId(paper.id)}>
      <div className="paper-card-top"><span>{paper.venue} · {paper.year || t.noYear}</span><span>{paperStatusLabel(paper.status)}</span></div>
      <h3>{paper.title}</h3>
      {paper.abstract && <p className="abstract-snippet">{paper.abstract.slice(0, 360)}</p>}
      <div className="tag-cloud"><span>{priorityLabel(paper.priority)}</span>{paper.reading_purpose && <span>{readingPurposeLabel(paper.reading_purpose)}</span>}{paper.reading_mode && <span>{readingModeLabel(paper.reading_mode)}</span>}{(paper.zotero_item_key || paper.zotero_key) && <span>{zoteroSyncLabel(paper)}</span>}{paper.pdf_source && <span>{pdfSourceLabel(paper.pdf_source)}</span>}</div>
      {renderPdfAssist(paper)}
      <div className="toolbar" onClick={(event) => event.stopPropagation()}>{actions}</div>
    </article>;
  }

  return (
    <section className="literature-workbench">
      <div className="panel literature-toolbar-panel">
        <div className="panel-heading"><h2>文献工作流</h2><span>文献检索 → 候选文献 → Zotero 文献库 → 阅读队列 → 阅读笔记</span></div>
        <div className="tabs">{literatureSections.map((item) => <button key={item} className={section === item ? "active-pill" : ""} onClick={() => setSection(item)}>{literatureSectionLabels[item]}</button>)}</div>
      </div>

      {section === "Search" && <div className="literature-search-stack">
        <div className="panel literature-search-panel">
          <h2>{t.searchTitle}</h2>
          <div className="form-grid paper-search refined-search">
            <label><span>来源</span><select value={venue} onChange={(event) => setVenue(event.target.value)}><option value="">全部来源</option>{venues.map((item) => <option key={item} value={item}>{item}</option>)}</select></label>
            <label><span>起始年份</span><input value={fromYear} onChange={(event) => setFromYear(event.target.value)} /></label>
            <label><span>结束年份</span><input value={toYear} onChange={(event) => setToYear(event.target.value)} /></label>
            <label><span>排序</span><select value={sort} onChange={(event) => setSort(event.target.value)}><option value="relevance">相关度</option><option value="newest">最新优先</option></select></label>
            <label className="search-query-field"><span>主题</span><input value={query} onChange={(event) => setQuery(event.target.value)} /></label>
            <label className="search-keywords-field"><span>关键词</span><textarea value={keywords} onChange={(event) => setKeywords(event.target.value)} /></label>
            <button className="primary" onClick={() => void search()}><Search size={16} />{t.search}</button>
          </div>
        </div>
        <div className="panel literature-results-panel">
          <div className="panel-heading compact-heading result-list-heading"><h2>{t.results}</h2></div>
          <div className="paper-grid workflow-result-grid">{visibleResults.map((paper) => {
            const key = resultKey(paper);
            const selected = Boolean(selectedResults[key]);
            return <article className={`paper-card paper-workflow-card literature-result-row ${selected ? "selected" : ""}`} key={key}>
              <label className="result-select" aria-label={`选择文献：${paper.title}`}><input type="checkbox" checked={selected} onChange={(event) => toggleResultSelection(paper, event.target.checked)} /></label>
              <div className="result-main">
                <div className="paper-card-top"><span>{paper.source_label || paper.venue || t.unknown} · {paper.year || t.noYear}</span><span>{Math.round(paper.relevance * 100)}%</span></div>
                <h3>{paper.title}</h3>
                {paper.translated_title && <p className="muted">{paper.translated_title}</p>}
                <p className="paper-authors">{paper.authors.slice(0, 8).join(", ")}</p>
              </div>
              {paper.abstract && <p className="abstract-snippet">{paper.abstract.slice(0, 360)}</p>}
              <div className="tag-cloud result-tags">{paper.matched_keywords.map((tag) => <span key={tag}>{tag}</span>)}{paper.pdf_url && <span>PDF</span>}</div>
              <div className="toolbar result-actions"><button onClick={() => setIgnored({ ...ignored, [key]: true })}><X size={16} />忽略</button><button onClick={() => void saveCandidate(paper)}><Save size={16} />候选</button><button onClick={() => void addResultToLibrary(paper)}><Send size={16} />Zotero / 文献库</button>{paper.url && <a href={paper.url} target="_blank"><Link size={16} />{t.open}</a>}</div>
            </article>;
          })}</div>
        </div>
      </div>}
      {section === "Search" && visibleResults.length > 0 && <div className="floating-bulk-actions" role="status" aria-live="polite">
        <strong>已选择 {selectedResultList.length} 篇</strong>
        <div className="toolbar">
          <button disabled={!visibleResults.length} onClick={selectVisibleResults}>全选当前结果</button>
          <button disabled={!selectedResultList.length} onClick={() => setSelectedResults({})}><X size={16} />清空选择</button>
          <button disabled={!selectedResultList.length} onClick={() => void saveSelectedCandidates()}><Save size={16} />批量候选</button>
          <button className="primary" disabled={!selectedResultList.length} onClick={() => void addSelectedToLibrary()}><Send size={16} />批量加入 Zotero</button>
        </div>
      </div>}

      {section === "Candidates" && <div className="paper-grid">{candidates.map((paper) => renderPaperRow(paper, <><button onClick={() => void updatePaperStatus(paper, "Dropped")}><X size={16} />移除</button><button onClick={() => void api.addExistingPaperToZotero(paper.id).then((saved) => { setSelectedPaperId(saved.id); setMessage("已添加到 Zotero 和文献库。"); return refresh(); })}><Send size={16} />Zotero / 文献库</button><button onClick={() => void queuePaper(paper)}><Clock3 size={16} />加入队列</button></>))}</div>}

      {section === "Library" && <div className="literature-grid">
        <div className="panel compact-filter-panel"><div className="panel-heading compact-heading"><h2>{t.saved}</h2><button onClick={() => void syncZotero()}><RefreshCw size={16} />同步 Zotero</button></div><div className="tabs">{["", ...venues].map((item) => <button key={item || "all"} className={venue === item ? "active-pill" : ""} onClick={() => setVenue(item)}>{item || t.all}</button>)}</div><div className="tabs">{["", ...topicFilters].map((item) => <button key={item || "all-topics"} className={topic === item ? "active-pill" : ""} onClick={() => setTopic(item)}>{item || "全部主题"}</button>)}</div></div>
        <div className="paper-grid literature-library-grid">{filteredLibrary.map((paper) => renderPaperRow(paper, <><button onClick={() => void queuePaper(paper)}><Clock3 size={16} />加入队列</button><button onClick={() => void createNote(paper)}><NotebookPen size={16} />笔记</button>{(paper.zotero_item_key || paper.zotero_key) && <button onClick={() => void checkZoteroForPaper(paper)}><RefreshCw size={16} />Check Zotero</button>}{zoteroItemUri(paper) && <a href={zoteroItemUri(paper)!}><BookOpen size={16} />Open in Zotero</a>}{zoteroAttachmentUri(paper) && <a href={zoteroAttachmentUri(paper)!}><Eye size={16} />Open PDF</a>}{!paper.zotero_pdf_attached && (paper.zotero_item_key || paper.zotero_key) && <label className="file-action-button"><UploadCloud size={16} />Attach Local PDF<input type="file" accept="application/pdf,.pdf" onChange={(event) => void attachPdfFile(paper, event.currentTarget.files?.[0] || null)} /></label>}{paperArticleUrl(paper) && <a href={paperArticleUrl(paper)!} target="_blank"><Link size={16} />Open Article in Browser</a>}</>, "library-row-card"))}</div>
      </div>}

      {section === "Reading Queue" && <div className="literature-grid">
        <div className="panel queue-control-panel"><h2>队列设置</h2><div className="form-grid"><label><span>优先级</span><select value={queueForm.priority} onChange={(event) => setQueueForm({ ...queueForm, priority: event.target.value })}>{paperPriorities.map((item) => <option key={item} value={item}>{priorityLabel(item)}</option>)}</select></label><label><span>阅读目的</span><select value={queueForm.reading_purpose} onChange={(event) => setQueueForm({ ...queueForm, reading_purpose: event.target.value })}>{readingPurposes.map((item) => <option key={item} value={item}>{readingPurposeLabel(item)}</option>)}</select></label><label><span>关联项目</span><select value={queueForm.related_project_id} onChange={(event) => setQueueForm({ ...queueForm, related_project_id: event.target.value })}><option value="">不关联项目</option>{projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}</select></label><label><span>阅读模式</span><select value={queueForm.reading_mode} onChange={(event) => setQueueForm({ ...queueForm, reading_mode: event.target.value })}>{readingModes.map((item) => <option key={item} value={item}>{readingModeLabel(item)}</option>)}</select></label></div></div>
        <div className="paper-grid reading-queue-grid">{queue.map((paper) => renderPaperRow(paper, <><select value={paper.status} onChange={(event) => void updatePaperStatus(paper, event.target.value)}>{readingStatuses.map((item) => <option key={item} value={item}>{paperStatusLabel(item)}</option>)}</select><select value={paper.reading_mode || ""} onChange={(event) => void updatePaperMode(paper, event.target.value)}><option value="">阅读模式</option>{readingModes.map((item) => <option key={item} value={item}>{readingModeLabel(item)}</option>)}</select><button onClick={() => void createNote(paper)}><NotebookPen size={16} />笔记</button></>, "reading-queue-card"))}</div>
      </div>}

      {section === "Reading Notes" && <div className="literature-grid note-workbench-grid">
        <div className="panel note-paper-list"><h2>文献</h2><div className="list compact-cards">{library.map((paper) => <button className="list-item" key={paper.id} onClick={() => setSelectedPaperId(paper.id)}><strong>{paper.title}</strong><span>{paperStatusLabel(paper.status)} · {paper.reading_mode ? readingModeLabel(paper.reading_mode) : "未设置阅读模式"}</span></button>)}</div></div>
        <div className="panel note-editor-panel"><div className="panel-heading"><h2>阅读笔记</h2><div className="toolbar">{selectedPaper && <button onClick={() => void createNote(selectedPaper)}><Plus size={16} />新建</button>}<button disabled={!selectedNote} onClick={() => void saveNote()}><Save size={16} />保存</button><button disabled={!selectedNote} onClick={() => void exportNote()}><UploadCloud size={16} />导出 .md</button><button disabled={!selectedPaper} onClick={() => void startReadingFocus()}><Timer size={16} />开始阅读</button></div></div>{selectedPaper && <div className="paper-detail-strip"><strong>{selectedPaper.title}</strong><span>{selectedPaper.venue} · {selectedPaper.year || t.noYear}</span><span>Zotero：{selectedPaper.zotero_item_key || selectedPaper.zotero_key || "未关联"}</span></div>}<div className="form-grid"><label><span>一句话总结</span><textarea value={noteSummary} onChange={(event) => setNoteSummary(event.target.value)} /></label><label><span>与我的研究相关性</span><textarea value={noteRelevance} onChange={(event) => setNoteRelevance(event.target.value)} /></label><label className="full-field"><span>Markdown 笔记</span><textarea className="large note-template" value={noteDraft} onChange={(event) => setNoteDraft(event.target.value)} /></label></div></div>
      </div>}

      {section === "Collections" && <div className="panel"><h2>合集</h2><div className="collection-grid">{venues.map((item) => <button key={item} onClick={() => { setVenue(item); setSection("Library"); }}><strong>{item}</strong><span>{papers.filter((paper) => paper.venue === item).length} 篇文献</span></button>)}</div><div className="tag-cloud collection-tags">{topicFilters.map((item) => <button key={item} onClick={() => { setTopic(item); setSection("Library"); }}>{item}</button>)}</div></div>}
    </section>
  );
}

