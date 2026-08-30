import { ui } from "./i18n";
import type { Lang } from "./i18n";
import type { Paper, SearchPaper } from "./types";

const zhWeekdayLabels = ["一", "二", "三", "四", "五", "六", "日"];
const enWeekdayLabels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function formatInputDate(date: Date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function formatDisplayDate(date: Date, lang: Lang = "zh") {
  const enWeek = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"][date.getDay()];
  const zhWeek = ["星期日", "星期一", "星期二", "星期三", "星期四", "星期五", "星期六"][date.getDay()];
  const week = lang === "zh" ? zhWeek : enWeek;
  return `${date.getFullYear()} / ${String(date.getMonth() + 1).padStart(2, "0")} / ${String(date.getDate()).padStart(2, "0")} · ${week}`;
}

function shiftMonth(dateValue: string, step: number) {
  const date = new Date(`${dateValue}T00:00:00`);
  date.setMonth(date.getMonth() + step);
  date.setDate(1);
  return formatInputDate(date);
}

function getMonthDays(dateValue: string) {
  const base = new Date(`${dateValue}T00:00:00`);
  const first = new Date(base.getFullYear(), base.getMonth(), 1);
  const start = new Date(first);
  const offset = (first.getDay() + 6) % 7;
  start.setDate(first.getDate() - offset);
  return Array.from({ length: 42 }, (_, index) => {
    const day = new Date(start);
    day.setDate(start.getDate() + index);
    return {
      key: `${formatInputDate(day)}-${index}`,
      date: formatInputDate(day),
      day: day.getDate(),
      inMonth: day.getMonth() === base.getMonth(),
    };
  });
}
const projectStatusLabels: Record<string, string> = {
  Total: "总数",
  Planning: "规划中",
  Active: "进行中",
  Blocked: "阻塞",
  Paused: "暂停",
  Completed: "已完成",
  Archived: "已归档",
};

const projectTabLabels: Record<string, string> = {
  overview: "概览",
  progress: "进度",
  git: "Git",
  versions: "版本",
  settings: "设置",
};

const stageStatusLabels: Record<string, string> = {
  pending: "待开始",
  active: "进行中",
  completed: "已完成",
  blocked: "阻塞",
};

const detectionLabels: Record<string, string> = {
  git_repository: "Git 仓库",
  github_remote: "GitHub 远程仓库",
  github_config: "GitHub 配置",
  ros2: "ROS2",
  robotics_assets: "机器人模型资源",
  python: "Python",
  node: "Node",
  cpp: "C/C++",
  docker: "Docker",
  readme: "README",
};

function projectStatusText(value?: string | null) {
  return value ? projectStatusLabels[value] || value : "未知";
}

function stageStatusText(value?: string | null) {
  return value ? stageStatusLabels[value] || value : "未知";
}

function healthText(value?: string | null) {
  if (value === "Healthy") return "健康";
  if (value === "Needs Attention") return "需要关注";
  if (value === "Blocked") return "阻塞";
  return value || "未知";
}

function registrationCaseText(value?: string | null) {
  if (value === "Local + Git + GitHub") return "本地 + Git + GitHub";
  if (value === "Local + Git") return "本地 + Git";
  if (value === "Local Only") return "仅本地目录";
  return value || "未知";
}

function statusLabel(t: typeof ui.zh.dashboard, status: string) {
  const labels: Record<string, string> = {
    planning: t.planning,
    active: t.active,
    blocked: t.blocked,
    paused: t.paused,
    completed: t.completed,
    archived: t.archived,
  };
  return labels[status] ?? status;
}

function formatDuration(seconds: number) {
  const safe = Math.max(0, Math.floor(seconds));
  const hours = Math.floor(safe / 3600);
  const minutes = Math.floor((safe % 3600) / 60);
  const secs = safe % 60;
  return [hours, minutes, secs].map((part) => String(part).padStart(2, "0")).join(":");
}

function githubWebUrl(remoteUrl: string) {
  if (remoteUrl.startsWith("git@github.com:")) {
    return `https://github.com/${remoteUrl.replace("git@github.com:", "").replace(/\.git$/, "")}`;
  }
  return remoteUrl.replace(/\.git$/, "");
}

function normalizePaperStatus(value?: string | null) {
  const key = (value || "Inbox").toLowerCase().replace(/_/g, " ");
  const labels: Record<string, string> = {
    inbox: "Inbox",
    candidate: "Candidate",
    "to read": "To Read",
    skimming: "Skimming",
    reading: "Reading",
    "deep reading": "Deep Reading",
    finished: "Finished",
    reference: "Reference",
    dropped: "Dropped",
  };
  return labels[key] || value || "Inbox";
}

function resultKey(paper: SearchPaper) {
  return paper.doi || paper.id;
}

async function fileStartsWithPdf(file: File): Promise<boolean> {
  const header = new Uint8Array(await file.slice(0, 5).arrayBuffer());
  return String.fromCharCode(...header) === "%PDF-";
}

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = String(reader.result || "");
      resolve(result.includes(",") ? result.split(",", 2)[1] : result);
    };
    reader.onerror = () => reject(reader.error || new Error("读取 PDF 文件失败。"));
    reader.readAsDataURL(file);
  });
}

function zoteroSyncLabel(paper: Paper) {
  if (!(paper.zotero_item_key || paper.zotero_key)) return "未同步 Zotero";
  if (paper.zotero_pdf_attached) return "Zotero：PDF 已挂载";
  const status = (paper.pdf_status || paper.zotero_pdf_status || "UNKNOWN").toUpperCase();
  const labels: Record<string, string> = {
    NONE: "Zotero：未发现 PDF",
    SEARCHING: "Zotero：正在查找 PDF",
    AVAILABLE: "Zotero：PDF 可用",
    ATTACHED: "Zotero：PDF 已挂载",
    BROWSER_REQUIRED: "需要浏览器打开",
    AUTH_REQUIRED: "需要登录/机构权限",
    FAILED: "自动获取失败",
    UNKNOWN: "Zotero：等待同步",
  };
  return labels[status] || "Zotero：等待同步";
}

function pdfAssistTitle(paper: Paper) {
  const status = (paper.pdf_status || paper.zotero_pdf_status || "").toUpperCase();
  if (status === "AUTH_REQUIRED") return "PDF 无法自动获取：需要登录或机构权限。";
  if (status === "BROWSER_REQUIRED") return "PDF 无法自动获取：需要浏览器环境。";
  return "PDF 无法自动获取。";
}

function pdfSourceLabel(value?: string | null) {
  const labels: Record<string, string> = {
    DIRECT_DOWNLOAD: "PDF 来源：直链",
    OPEN_ACCESS: "PDF 来源：开放获取",
    ARXIV: "PDF 来源：arXiv 预印本",
    OPENALEX: "PDF 来源：OpenAlex",
    SEMANTIC_SCHOLAR: "PDF 来源：Semantic Scholar",
    ZOTERO_CONNECTOR: "PDF 来源：Zotero Connector",
    ZOTERO: "PDF 来源：Zotero",
    LOCAL_FILE: "PDF 来源：本地挂载",
    MANUAL: "PDF 来源：手动",
    UNKNOWN: "PDF 来源：未知",
  };
  return labels[(value || "UNKNOWN").toUpperCase()] || labels.UNKNOWN;
}

function paperStatusLabel(value?: string | null) {
  const labels: Record<string, string> = {
    Inbox: "收件箱",
    Candidate: "候选文献",
    "To Read": "待读",
    Skimming: "略读中",
    Reading: "阅读中",
    "Deep Reading": "精读中",
    Finished: "已完成",
    Reference: "参考文献",
    Dropped: "已移除",
  };
  return labels[normalizePaperStatus(value)] || value || "收件箱";
}

function priorityLabel(value?: string | null) {
  const labels: Record<string, string> = { high: "高优先级", normal: "普通优先级", low: "低优先级" };
  return labels[(value || "normal").toLowerCase()] || value || "普通优先级";
}

function readingModeLabel(value?: string | null) {
  const labels: Record<string, string> = { SCAN: "快速浏览", SKIM: "略读", READ: "阅读", DEEP: "精读" };
  return labels[(value || "").toUpperCase()] || value || "未设置阅读模式";
}

function readingPurposeLabel(value?: string | null) {
  const labels: Record<string, string> = {
    Project: "项目相关",
    "Literature Review": "文献综述",
    "Learn Method": "学习方法",
    Reproduce: "复现",
    "Compare Baseline": "对比基线",
    "Research Idea": "研究想法",
    "General Interest": "一般兴趣",
  };
  return labels[value || "General Interest"] || value || "一般兴趣";
}

function taskPriorityLabel(value?: string | null) {
  const labels: Record<string, string> = { high: "高优先级", medium: "中优先级", low: "低优先级" };
  return labels[(value || "medium").toLowerCase()] || value || "中优先级";
}

function taskStatusLabel(value?: string | null) {
  const labels: Record<string, string> = { todo: "待办", doing: "进行中", done: "已完成" };
  return labels[(value || "todo").toLowerCase()] || value || "待办";
}


function friendlyError(error: unknown) {
  const message = error instanceof Error ? error.message : String(error);
  try {
    const parsed = JSON.parse(message);
    if (parsed?.detail) return parsed.detail;
  } catch {
    // Keep the original message when it is not a JSON API error.
  }
  return message;
}

export {
  zhWeekdayLabels,
  enWeekdayLabels,
  formatInputDate,
  formatDisplayDate,
  shiftMonth,
  getMonthDays,
  projectStatusLabels,
  projectTabLabels,
  stageStatusLabels,
  detectionLabels,
  projectStatusText,
  stageStatusText,
  healthText,
  registrationCaseText,
  statusLabel,
  formatDuration,
  githubWebUrl,
  normalizePaperStatus,
  resultKey,
  fileToBase64,
  fileStartsWithPdf,
  zoteroSyncLabel,
  pdfAssistTitle,
  pdfSourceLabel,
  paperStatusLabel,
  priorityLabel,
  readingModeLabel,
  readingPurposeLabel,
  taskPriorityLabel,
  taskStatusLabel,
  friendlyError,
};
