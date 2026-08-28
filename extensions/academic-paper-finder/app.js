const API_CANDIDATES = ["http://127.0.0.1:8766", "http://localhost:8766", "http://127.0.0.1:8765", "http://localhost:8765"];
let activeApiBase = API_CANDIDATES[0];

const defaultSources = [
  {
    id: "icra",
    label: "ICRA",
    kind: "conference",
    aliases: ["IEEE International Conference on Robotics and Automation"],
    openalex_ids: []
  },
  {
    id: "iros",
    label: "IROS",
    kind: "conference",
    aliases: ["IEEE/RSJ International Conference on Intelligent Robots and Systems"],
    openalex_ids: []
  },
  {
    id: "ral",
    label: "RA-L",
    kind: "journal",
    aliases: ["IEEE Robotics and Automation Letters"],
    openalex_ids: []
  },
  {
    id: "science-robotics",
    label: "Science Robotics",
    kind: "journal",
    aliases: ["Science Robotics"],
    openalex_ids: []
  },
  {
    id: "tro",
    label: "T-RO",
    kind: "journal",
    aliases: ["IEEE Transactions on Robotics"],
    openalex_ids: []
  }
];

const defaultKeywords = [
  "embodied intelligence",
  "embodied AI",
  "embodied agent",
  "task planning",
  "robot task planning",
  "world model",
  "world models",
  "WM",
  "WAM",
  "vision-language-action",
  "VLA",
  "vision-language model",
  "VLM"
];

let papers = [];
let selected = new Map();

const elements = {
  apiStatus: document.getElementById("apiStatus"),
  sourceList: document.getElementById("sourceList"),
  fromYear: document.getElementById("fromYear"),
  toYear: document.getElementById("toYear"),
  keywords: document.getElementById("keywords"),
  query: document.getElementById("query"),
  searchButton: document.getElementById("searchButton"),
  exportButton: document.getElementById("exportButton"),
  resultCount: document.getElementById("resultCount"),
  selectedCount: document.getElementById("selectedCount"),
  message: document.getElementById("message"),
  results: document.getElementById("results")
};

function init() {
  renderSources();
  elements.keywords.value = defaultKeywords.join("\n");
  elements.query.value = "embodied intelligence robot task planning world model";
  elements.searchButton.addEventListener("click", search);
  elements.exportButton.addEventListener("click", importToZotero);
  checkApi();
}

async function checkApi() {
  for (const baseUrl of API_CANDIDATES) {
    try {
      const response = await fetch(`${baseUrl}/health`, { cache: "no-store" });
      const data = await response.json();
      if (data.ok) {
        activeApiBase = baseUrl;
        const translation = data.translation?.configured
          ? `翻译：${data.translation.provider}`
          : "翻译：未配置";
        elements.apiStatus.textContent = `本地后台已连接：${baseUrl} · ${translation}`;
        elements.apiStatus.className = data.translation?.configured ? "ok" : "warn";
        return true;
      }
    } catch {
      // Try the next loopback hostname.
    }
  }
  elements.apiStatus.textContent = "未连接后台，请启动 8765 服务并重新加载插件";
  elements.apiStatus.className = "warn";
  return false;
}

function renderSources() {
  elements.sourceList.textContent = "";
  for (const source of defaultSources) {
    const label = document.createElement("label");
    label.className = "check-row";

    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.value = source.id;
    checkbox.checked = true;

    const name = document.createElement("span");
    name.textContent = source.label;

    const kind = document.createElement("small");
    kind.textContent = source.kind === "journal" ? "期刊" : "会议";

    label.append(checkbox, name, kind);
    elements.sourceList.appendChild(label);
  }
}

function selectedSources() {
  const checked = [...elements.sourceList.querySelectorAll("input:checked")].map((input) => input.value);
  return defaultSources.filter((source) => checked.includes(source.id));
}

function keywordList() {
  return elements.keywords.value
    .split(/\n|,/)
    .map((value) => value.trim())
    .filter(Boolean);
}

async function search() {
  setMessage("正在检索 OpenAlex...");
  elements.searchButton.disabled = true;
  try {
    const apiReady = await checkApi();
    if (!apiReady) {
      throw new Error("无法连接本地后台。确认终端里 Uvicorn 正在监听 http://127.0.0.1:8765，然后在 about:debugging 里重新加载插件。");
    }

    const response = await fetch(`${activeApiBase}/papers/search`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        query: elements.query.value,
        sources: selectedSources(),
        keywords: keywordList(),
        from_year: Number(elements.fromYear.value),
        to_year: Number(elements.toYear.value),
        per_source_limit: 25
      })
    });
    if (!response.ok) {
      throw new Error(await response.text());
    }
    const data = await response.json();
    papers = data.papers || [];
    selected = new Map();
    renderResults();
    setMessage(papers.length ? "" : "没有检索到结果，可以放宽关键词或年份。");
  } catch (error) {
    setMessage(`检索失败：${friendlyError(error)}`);
  } finally {
    elements.searchButton.disabled = false;
  }
}

function renderResults() {
  elements.resultCount.textContent = `${papers.length} 篇结果`;
  updateSelectedCount();
  elements.results.textContent = "";
  for (const paper of papers) {
    const card = document.createElement("article");
    card.className = "paper-card";
    const authors = paper.authors?.length ? paper.authors.join(", ") : "作者信息暂缺";
    const abstract = paper.abstract || "摘要暂缺";
    const translatedTitle = paper.translated_title || "未配置翻译服务";
    const translatedAbstract = paper.translated_abstract || "未配置翻译服务";
    const matchedKeywords = paper.matched_keywords?.length ? paper.matched_keywords.join(" / ") : "暂无关键词命中";

    const head = document.createElement("div");
    head.className = "paper-head";

    const label = document.createElement("label");
    label.className = "select-paper";

    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.dataset.id = paperKey(paper);

    const source = document.createElement("span");
    source.textContent = `${paper.source_label || paper.venue || "Unknown"} · ${paper.year || "年份未知"}`;

    const score = document.createElement("strong");
    score.textContent = `${Math.round((paper.relevance || 0) * 100)}%`;

    label.append(checkbox, source);
    head.append(label, score);

    const title = document.createElement("h2");
    title.textContent = paper.title;

    const titleCn = document.createElement("p");
    titleCn.className = "translated";
    titleCn.textContent = translatedTitle;

    const authorLine = document.createElement("p");
    authorLine.className = "authors";
    authorLine.textContent = authors;

    const details = document.createElement("details");
    const summary = document.createElement("summary");
    summary.textContent = "摘要与翻译";
    const abstractText = document.createElement("p");
    abstractText.textContent = abstract;
    const abstractCn = document.createElement("p");
    abstractCn.className = "translated";
    abstractCn.textContent = translatedAbstract;
    details.append(summary, abstractText, abstractCn);

    const meta = document.createElement("div");
    meta.className = "meta";
    const access = document.createElement("span");
    access.textContent = paper.is_oa ? "OA 可用" : "可能需要 CARSI";
    const keywords = document.createElement("span");
    keywords.textContent = matchedKeywords;
    meta.append(access, keywords);
    if (paper.doi) {
      const doi = document.createElement("span");
      doi.textContent = `DOI ${paper.doi}`;
      meta.appendChild(doi);
    }

    const actions = document.createElement("div");
    actions.className = "actions";
    const openPaper = document.createElement("button");
    openPaper.dataset.open = paper.url || doiUrl(paper.doi);
    openPaper.textContent = "打开原文";
    actions.appendChild(openPaper);
    if (paper.pdf_url) {
      const openPdf = document.createElement("button");
      openPdf.dataset.open = paper.pdf_url;
      openPdf.textContent = "打开 PDF";
      actions.appendChild(openPdf);
    }

    card.append(head, title, titleCn, authorLine, details, meta, actions);

    checkbox.addEventListener("change", (event) => {
      const key = paperKey(paper);
      if (event.target.checked) {
        selected.set(key, paper);
      } else {
        selected.delete(key);
      }
      updateSelectedCount();
    });
    for (const button of card.querySelectorAll("button[data-open]")) {
      button.addEventListener("click", () => openUrl(button.dataset.open));
    }
    elements.results.appendChild(card);
  }
}

async function importToZotero() {
  const chosen = [...selected.values()];
  if (!chosen.length) {
    setMessage("请先勾选需要加入 Zotero 的论文。");
    return;
  }
  setMessage("正在连接 Zotero。如果 Zotero 弹出授权窗口，请点击 Allow 或 Always Allow...");
  try {
    const apiReady = await checkApi();
    if (!apiReady) {
      throw new Error("无法连接本地后台。");
    }
    const response = await fetch(`${activeApiBase}/papers/import-zotero`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        collection_root: "Embodied Intelligence Papers",
        papers: chosen
      })
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || JSON.stringify(data));
    }
    const pendingCount = data.pending_pdfs?.length || 0;
    if (pendingCount) {
      await browser.runtime.sendMessage({
        type: "START_CARSI_PDF_CAPTURE",
        pendingPdfs: data.pending_pdfs,
        apiBase: activeApiBase
      });
      setMessage(`${data.message} 已创建/使用 ${Object.keys(data.collections || {}).length - 1} 个来源分类。PDF 附件：${data.attached_pdfs || 0} 个。${pendingCount} 个 PDF 已加入获取队列，将一次只打开 1 个页面。`);
    } else {
      setMessage(`${data.message} 已创建/使用 ${Object.keys(data.collections || {}).length - 1} 个来源分类。PDF 附件：${data.attached_pdfs || 0} 个。`);
    }
  } catch (error) {
    setMessage(`Zotero 提交失败：${friendlyError(error)}`);
  }
}


function paperKey(paper) {
  const doi = normalizeDoi(paper.doi);
  if (doi) return `doi:${doi}`;
  const title = String(paper.title || "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim()
    .replace(/\s+/g, " ");
  const year = paper.year || "";
  if (title) return `title:${title}|year:${year}`;
  return `id:${paper.id}`;
}

function normalizeDoi(doi) {
  return String(doi || "")
    .trim()
    .toLowerCase()
    .replace(/^https?:\/\/doi\.org\//, "")
    .replace(/^doi:/, "");
}

function updateSelectedCount() {
  elements.selectedCount.textContent = `已选择 ${selected.size} 篇`;
}

function setMessage(text) {
  elements.message.textContent = text;
  elements.message.hidden = !text;
}

function doiUrl(doi) {
  return doi ? `https://doi.org/${doi}` : "";
}

function openUrl(url) {
  if (!url) return;
  browser.runtime.sendMessage({ type: "OPEN_URL", url });
}

function friendlyError(error) {
  const message = error?.message || String(error);
  if (message.includes("NetworkError") || message.includes("Failed to fetch")) {
    return "浏览器无法访问本地后台。请确认后台已启动，并在 Firefox 的 about:debugging 页面点击“重新载入”插件。";
  }
  return message;
}

function escapeHtml(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function escapeAttr(value) {
  return escapeHtml(value).replaceAll("`", "&#096;");
}

init();
