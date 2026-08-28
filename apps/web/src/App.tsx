import { useEffect, useMemo, useState, type ReactNode } from "react";
import {
  BarChart3,
  AlertTriangle,
  BookOpen,
  Boxes,
  CalendarDays,
  Check,
  ChevronLeft,
  ChevronRight,
  Eye,
  Circle,
  CircleCheck,
  Clock3,
  FlaskConical,
  FolderOpen,
  GitBranch,
  GitCommitHorizontal,
  History,
  Languages,
  LayoutDashboard,
  Link,
  Loader2,
  Pause,
  Play,
  NotebookPen,
  PenLine,
  Plus,
  RefreshCw,
  RotateCcw,
  Save,
  Search,
  Send,
  Settings as SettingsIcon,
  ShieldCheck,
  SlidersHorizontal,
  Timer,
  UploadCloud,
  Trash2,
  X,
} from "lucide-react";
import { api } from "./api";
import type { DashboardSummary, DirectoryListing, Experiment, FocusSession, GitCommit, KnowledgeLink, Paper, Project, ProjectProgress, ProjectScan, ProjectStage, ReadingNote, SearchPaper, Summary, SystemSettings, Task } from "./types";

const venues = ["ICRA", "IROS", "RA-L", "T-RO", "Science Robotics", "Others"];
const defaultSources = [
  { id: "icra", label: "ICRA", kind: "conference", aliases: ["IEEE International Conference on Robotics and Automation"], openalex_ids: [] },
  { id: "iros", label: "IROS", kind: "conference", aliases: ["IEEE/RSJ International Conference on Intelligent Robots and Systems"], openalex_ids: [] },
  { id: "ral", label: "RA-L", kind: "journal", aliases: ["IEEE Robotics and Automation Letters"], openalex_ids: [] },
  { id: "science-robotics", label: "Science Robotics", kind: "journal", aliases: ["Science Robotics"], openalex_ids: [] },
  { id: "tro", label: "T-RO", kind: "journal", aliases: ["IEEE Transactions on Robotics"], openalex_ids: [] },
];

type Lang = "zh" | "en";
type Tab = "dashboard" | "study" | "projects" | "papers" | "knowledge" | "research" | "review" | "notes" | "experiments" | "settings";


const coreModuleRows = {
  zh: [
    { key: "Dashboard", manages: "每天真正要看的首页", content: "今日任务 / 本周目标 / 项目进度 / 待读论文", status: "covered" },
    { key: "学习 & 生活", manages: "日程和个人节奏", content: "课程 / 学习计划 / 英语 / 运动 / 会议", status: "covered" },
    { key: "Projects", manages: "机器人科研项目", content: "VLA / 导航 / Manipulation / ROS2 / 实验记录", status: "covered" },
    { key: "Papers", manages: "文献管理", content: "阅读队列 / 精读笔记 / Related Work / 引用", status: "covered" },
    { key: "Knowledge", manages: "长期知识库", content: "SLAM / RL / Transformer / 控制 / ROS2", status: "covered" },
    { key: "Research & Writing", manages: "论文研究全过程", content: "Idea / 实验 / Figure / 草稿 / 投稿", status: "covered" },
    { key: "Review", manages: "周/月/学期复盘", content: "项目进展 / 阅读量 / 实验结果 / 下阶段计划", status: "covered" },
  ],
  en: [
    { key: "Dashboard", manages: "Daily home view", content: "Today tasks / weekly goals / project progress / paper queue", status: "covered" },
    { key: "Study & Life", manages: "Schedule and personal rhythm", content: "Courses / study plan / English / workout / meetings", status: "covered" },
    { key: "Projects", manages: "Robotics research projects", content: "VLA / navigation / manipulation / ROS2 / experiment log", status: "covered" },
    { key: "Papers", manages: "Literature management", content: "Reading queue / intensive notes / Related Work / citations", status: "covered" },
    { key: "Knowledge", manages: "Long-term knowledge base", content: "SLAM / RL / Transformer / control / ROS2", status: "covered" },
    { key: "Research & Writing", manages: "Paper research pipeline", content: "Ideas / experiments / figures / draft / submission", status: "covered" },
    { key: "Review", manages: "Weekly, monthly, semester reviews", content: "Progress / reading volume / results / next plan", status: "covered" },
  ],
};

function useWorkbenchWidth() {
  const [width, setWidth] = useState(() => Math.min(1360, Math.max(920, window.innerWidth - 326)));
  useEffect(() => {
    const update = () => setWidth(Math.min(1360, Math.max(920, window.innerWidth - 326)));
    window.addEventListener("resize", update);
    return () => window.removeEventListener("resize", update);
  }, []);
  return width;
}

const ui = {
  zh: {
    subtitle: "具身智能科研操作台",
    tagline: "本地优先的论文、项目、实验与知识管理中心。",
    refresh: "刷新",
    connected: "本地工作台已连接",
    connecting: "正在连接本地工作台...",
    backendOffline: "后端未连接",
    nav: {
      dashboard: "总览",
      study: "学习 & 生活",
      projects: "项目",
      papers: "文献",
      knowledge: "知识库",
      research: "研究 & 写作",
      review: "复盘",
      notes: "阅读笔记",
      experiments: "实验",
      settings: "设置",
    },
    dashboard: {
      today: "今日",
      tasks: "任务",
      notes: "笔记",
      activeProjects: "活跃项目",
      paperQueue: "文献队列",
      papers: "论文",
      inbox: "收件箱",
      experiments: "实验记录",
      capture: "快速记录",
      knowledge: "知识链接",
      moduleAudit: "模块核对",
      covered: "已覆盖",
      childModule: "子模块",
      captureText: "想法：\nBug：\n论文：\n实验：\n会议记录：",
      todayDate: "今日日期",
      currentTime: "当前时间",
      calendar: "日历",
      previousMonth: "上个月",
      nextMonth: "下个月",
      selectedDayTasks: "当日任务",
      importantThree: "今日最重要的 3 件事",
      addTask: "添加任务",
      taskPlaceholder: "输入某日任务，例如：精读一篇 VLA 论文",
      markDone: "标记完成",
      reopen: "恢复待办",
      delete: "删除",
      noTasks: "这一天还没有任务。",
      projectProgress: "项目今日进展",
      chooseProject: "选择项目",
      stage: "当前阶段",
      stagePlaceholder: "例如：Baseline / Experiment / Development",
      completedToday: "今天完成了什么",
      completedPlaceholder: "一行一条，例如：\n跑通 baseline 训练脚本\n完成抓取实验 10 组",
      pendingNext: "还待完成什么",
      pendingPlaceholder: "一行一条，例如：\n整理实验指标\n补充失败样例分析",
      progressNote: "补充说明",
      saveProgress: "保存今日进展",
      noProgress: "这一天还没有项目进展记录。",
      overviewStats: "科研状态速览",
      motto: "要成功，先发疯，不顾一切向前冲",
      weekExecution: "本周执行率",
      doneTasks: "已完成任务",
      todayDone: "今日完成",
      focusStreak: "连续记录",
      backToCalendar: "返回日历",
      openDayTasks: "查看当日任务",
      dailyTasks: "当日任务",
      completionRate: "完成率",
      focus: "专注",
      enterFocus: "进入专注模式",
      todayFocus: "今日专注",
      weekFocus: "本周专注",
      focusIdle: "未专注",
      focusRunning: "专注中",
      focusPaused: "已暂停",
      projects: "项目",
      total: "总数",
      planning: "规划中",
      active: "进行中",
      blocked: "阻塞",
      paused: "暂停",
      completed: "已完成",
      archived: "已归档",
      currentMilestone: "当前阶段",
      nextMilestone: "下一阶段",
      viewModule: "进入模块",
      literature: "文献",
      toRead: "待读",
      reading: "阅读中",
      finished: "已完成",
      venues: "会议/期刊",
      currentlyReading: "正在阅读",
      recentlyFinished: "最近完成",
      running: "运行中",
      pending: "待处理",
      failed: "失败",
      researchIdeas: "研究想法",
      obsidianConnected: "Obsidian 已连接",
      obsidianDisconnected: "Obsidian 未连接",
      totalNotes: "知识条目",
      updatedThisWeek: "本周更新",
      recentlyUpdated: "最近更新",
      git: "Git / GitHub",
      modifiedFiles: "变更文件",
      unpushedCommits: "未推送提交",
      lastCommit: "最近提交",
      attention: "提醒",
      noAttention: "暂无需要关注的事项。",
      noItems: "暂无数据。",

    },

    study: {
      title: "学习与生活节奏",
      schedule: "今日安排",
      plan: "学习计划",
      wellbeing: "生活习惯",
      addTask: "添加任务",
      taskPlaceholder: "课程 / 英语 / 运动 / 会议",
      morning: "09:00 课程 / 论文阅读",
      afternoon: "14:00 实验 / Coding",
      evening: "19:30 英语 / 基础课",
      review: "21:30 Daily Review",
      habits: ["英语输入", "运动", "睡眠", "会议整理"],
    },
    projects: {
      registerTitle: "注册本地项目",
      projectName: "项目名称",
      projectPath: "/home/robot/项目目录",
      register: "注册",
      gitPanel: "Git 面板",
      gitStatus: "查看状态",
      push: "推送",
      branch: "分支",
      remote: "远程仓库",
      unknown: "未知",
      none: "无",
      commitMessage: "提交信息",
      commitSelected: "提交所选文件",
      commitOk: "已创建提交。",
      commitFailed: "提交失败。",
      pushOk: "推送完成。",
      pushFailed: "推送失败。",
    },
    papers: {
      searchTitle: "文献检索",
      search: "检索",
      importZotero: "导入 Zotero",
      saved: "已保存文献",
      all: "全部",
      results: "检索结果",
      found: "检索到",
      foundSuffix: "篇论文",
      failed: "检索失败",
      zoteroDone: "Zotero 导入完成。",
      unknown: "未知来源",
      noYear: "年份未知",
      save: "保存到工作台",
      open: "打开原文",
    },
    notes: {
      createTitle: "新建阅读笔记",
      defaultTitle: "阅读笔记",
      noPaper: "不关联论文",
      create: "创建笔记",
      listTitle: "阅读笔记",
      template: `# 文献阅读笔记\n\n## 1. 研究问题\n\n## 2. 动机\n\n## 3. 核心贡献\n\n## 4. 系统结构\n\n## 5. 方法\n\n## 6. 实验\n\n## 7. 我的理解\n\n## 8. 问题\n\n## 9. 局限性\n\n## 10. 我的想法\n\n## 11. 提取到知识库的内容\n`,
    },
    experiments: {
      newTitle: "新建实验",
      noProject: "不关联项目",
      result: "实验结果",
      conclusion: "结论",
      create: "创建实验",
      log: "实验日志",
      defaultTitle: "基线实验",
    },

    research: {
      pipeline: "论文研究 Pipeline",
      writingBoard: "写作看板",
      ideas: "研究想法",
      figures: "Figure Bank",
      relatedWork: "Related Work",
      draft: "Draft",
      revision: "Revision",
      submission: "Submission",
      ideaItems: ["从阅读笔记提取可实验问题", "关联项目与实验", "沉淀 Contributions"],
      figureItems: ["Fig 1 System Overview", "Fig 2 VLA Architecture", "Fig 3 Experiment Results"],
    },
    review: {
      moduleAudit: "核心模块核对",
      weekly: "周复盘",
      monthly: "月复盘",
      semester: "学期复盘",
      progress: "项目进展",
      reading: "阅读量",
      experiments: "实验结果",
      next: "下阶段计划",
      missingTitle: "原规划对照",
    },
    knowledge: {
      newTitle: "新建知识链接",
      create: "创建链接",
      listTitle: "知识库链接",
      openObsidian: "在 Obsidian 打开",
    },
    paperCard: {
      noYear: "年份未知",
      open: "打开论文",
    },

    settings: {
      title: "系统设置",
      general: "通用",
      integrations: "集成",
      paths: "路径与存储",
      appearance: "外观",
      advanced: "高级",
      language: "系统语言",
      chinese: "中文",
      english: "English",
      save: "保存设置",
      test: "测试连接",
      enabled: "启用",
      obsidian: "Obsidian",
      zotero: "Zotero",
      github: "GitHub",
      vaultPath: "Vault 路径",
      knowledgeRoot: "知识库根目录",
      useObsidianUri: "使用 Obsidian URI",
      connectionMode: "连接模式",
      userId: "User ID",
      apiKey: "API Key",
      library: "Library",
      username: "用户名",
      token: "Personal Access Token",
      defaultOwner: "默认 Owner",
      defaultBranch: "默认分支",
      projectsRoot: "项目根目录",
      datasetRoot: "数据集根目录",
      experimentRoot: "实验根目录",
      placeholderOnly: "暂时保留结构，后续再扩展。",
      saved: "设置已保存。",
    },
    focusMode: {
      title: "专注模式",
      currentTime: "当前时间",
      start: "开始专注",
      pause: "暂停",
      resume: "继续",
      finish: "结束专注",
      exit: "退出专注模式",
      task: "关联任务",
      project: "关联项目",
      noTask: "不关联任务",
      noProject: "不关联项目",
      noAssociation: "不关联任何内容",
      note: "备注",
      elapsed: "本次专注",
      today: "今日累计",
      week: "本周累计",
      running: "专注中",
      paused: "已暂停",
    },

  },
  en: {
    subtitle: "Embodied Research OS",
    tagline: "Local-first control center for papers, projects, experiments, and knowledge.",
    refresh: "刷新",
    connected: "Local workbench connected",
    connecting: "Connecting to local workbench...",
    backendOffline: "Backend offline",
    nav: {
      dashboard: "Dashboard",
      study: "Study & Life",
      projects: "Projects",
      papers: "Papers",
      knowledge: "Knowledge",
      research: "Research & Writing",
      review: "Review",
      notes: "Reading Notes",
      experiments: "Experiments",
      settings: "Settings",
    },
    dashboard: {
      today: "Today",
      tasks: "Tasks",
      notes: "Notes",
      activeProjects: "Active Projects",
      paperQueue: "Paper Queue",
      papers: "Papers",
      inbox: "Inbox",
      experiments: "Experiments",
      capture: "Quick Capture",
      knowledge: "Knowledge",
      moduleAudit: "Module Audit",
      covered: "Covered",
      childModule: "Child module",
      captureText: "Idea:\nBug:\nPaper:\nExperiment:\nMeeting note:",
      todayDate: "Date",
      currentTime: "Current Time",
      calendar: "Calendar",
      previousMonth: "Previous Month",
      nextMonth: "Next Month",
      selectedDayTasks: "Day Tasks",
      importantThree: "Top 3 Priorities",
      addTask: "Add Task",
      taskPlaceholder: "Task for this day, e.g. read one VLA paper",
      markDone: "Mark Done",
      reopen: "Reopen",
      delete: "Delete",
      noTasks: "No tasks for this day yet.",
      projectProgress: "Project Progress Today",
      chooseProject: "Choose Project",
      stage: "Current Stage",
      stagePlaceholder: "e.g. Baseline / Experiment / Development",
      completedToday: "Completed Today",
      completedPlaceholder: "One item per line, e.g.\nRan baseline training\nFinished 10 grasping trials",
      pendingNext: "Pending / Next",
      pendingPlaceholder: "One item per line, e.g.\nOrganize metrics\nAnalyze failure cases",
      progressNote: "Notes",
      saveProgress: "Save Progress",
      noProgress: "No progress logs for this day yet.",
      overviewStats: "Research Snapshot",
      motto: "Move the research forward, one focused block at a time",
      weekExecution: "Week Execution",
      doneTasks: "Completed Tasks",
      todayDone: "Today Done",
      focusStreak: "Focus Streak",
      backToCalendar: "Back to Calendar",
      openDayTasks: "Open Day Tasks",
      dailyTasks: "Day Tasks",
      completionRate: "Completion Rate",
      focus: "Focus",
      enterFocus: "Enter Focus Mode",
      todayFocus: "Today Focus",
      weekFocus: "Week Focus",
      focusIdle: "Idle",
      focusRunning: "Focusing",
      focusPaused: "Paused",
      projects: "Projects",
      total: "Total",
      planning: "Planning",
      active: "Active",
      blocked: "Blocked",
      paused: "Paused",
      completed: "Completed",
      archived: "Archived",
      currentMilestone: "Current Milestone",
      nextMilestone: "Next Milestone",
      viewModule: "Open Module",
      literature: "Literature",
      toRead: "To Read",
      reading: "Reading",
      finished: "Finished",
      venues: "Venues",
      currentlyReading: "Currently Reading",
      recentlyFinished: "Recently Finished",
      running: "Running",
      pending: "Pending",
      failed: "Failed",
      researchIdeas: "Research Ideas",
      obsidianConnected: "Obsidian Connected",
      obsidianDisconnected: "Obsidian Disconnected",
      totalNotes: "Knowledge Notes",
      updatedThisWeek: "Updated This Week",
      recentlyUpdated: "Recently Updated",
      git: "Git / GitHub",
      modifiedFiles: "Modified Files",
      unpushedCommits: "Unpushed Commits",
      lastCommit: "Last Commit",
      attention: "Attention",
      noAttention: "Nothing needs attention right now.",
      noItems: "No data yet.",

    },

    study: {
      title: "Study and Life Rhythm",
      schedule: "Today Schedule",
      plan: "Study Plan",
      wellbeing: "Life Habits",
      addTask: "Add Task",
      taskPlaceholder: "Course / English / workout / meeting",
      morning: "09:00 Course / paper reading",
      afternoon: "14:00 Experiment / coding",
      evening: "19:30 English / coursework",
      review: "21:30 Daily Review",
      habits: ["English input", "Workout", "Sleep", "Meeting notes"],
    },
    projects: {
      registerTitle: "注册本地项目",
      projectName: "项目名称",
      projectPath: "/home/robot/project",
      register: "Register",
      gitPanel: "Git Panel",
      gitStatus: "Git Status",
      push: "推送",
      branch: "Branch",
      remote: "Remote",
      unknown: "unknown",
      none: "无",
      commitMessage: "提交信息",
      commitSelected: "提交所选文件",
      commitOk: "提交已创建。",
      commitFailed: "Commit failed.",
      pushOk: "推送完成。",
      pushFailed: "推送 failed.",
    },
    papers: {
      searchTitle: "Paper Search",
      search: "Search",
      importZotero: "Import Zotero",
      saved: "Saved Papers",
      all: "All",
      results: "Search Results",
      found: "Found",
      foundSuffix: "papers",
      failed: "Search failed",
      zoteroDone: "Zotero import complete.",
      unknown: "未知",
      noYear: "No year",
      save: "Save",
      open: "Open",
    },
    notes: {
      createTitle: "Create Reading Note",
      defaultTitle: "Reading Note",
      noPaper: "No linked paper",
      create: "Create Note",
      listTitle: "Reading Notes",
      template: `# Paper Reading Note\n\n## 1. Research Problem\n\n## 2. Motivation\n\n## 3. Core Contribution\n\n## 4. Architecture\n\n## 5. Method\n\n## 6. Experiments\n\n## 7. My Understanding\n\n## 8. Questions\n\n## 9. Limitations\n\n## 10. Ideas\n\n## 11. Knowledge Extracted\n`,
    },
    experiments: {
      newTitle: "New Experiment",
      noProject: "No project",
      result: "Result",
      conclusion: "Conclusion",
      create: "Create Experiment",
      log: "Experiment Log",
      defaultTitle: "Baseline experiment",
    },

    research: {
      pipeline: "Research Paper Pipeline",
      writingBoard: "Writing Board",
      ideas: "Research Ideas",
      figures: "Figure Bank",
      relatedWork: "Related Work",
      draft: "Draft",
      revision: "Revision",
      submission: "Submission",
      ideaItems: ["Extract experimentable questions from reading notes", "Link projects and experiments", "Shape contributions"],
      figureItems: ["Fig 1 System Overview", "Fig 2 VLA Architecture", "Fig 3 Experiment Results"],
    },
    review: {
      moduleAudit: "Core Module Audit",
      weekly: "Weekly Review",
      monthly: "Monthly Review",
      semester: "Semester Review",
      progress: "Project Progress",
      reading: "Reading Volume",
      experiments: "Experiment Results",
      next: "Next Plan",
      missingTitle: "Original Plan Mapping",
    },
    knowledge: {
      newTitle: "New Knowledge Link",
      create: "Create Link",
      listTitle: "Knowledge Base Links",
      openObsidian: "Open in Obsidian",
    },
    paperCard: {
      noYear: "No year",
      open: "Open paper",
    },

    settings: {
      title: "System Settings",
      general: "General",
      integrations: "Integrations",
      paths: "Paths & Storage",
      appearance: "Appearance",
      advanced: "Advanced",
      language: "System Language",
      chinese: "中文",
      english: "English",
      save: "Save Settings",
      test: "Test Connection",
      enabled: "Enabled",
      obsidian: "Obsidian",
      zotero: "Zotero",
      github: "GitHub",
      vaultPath: "Vault Path",
      knowledgeRoot: "Knowledge Root",
      useObsidianUri: "Use Obsidian URI",
      connectionMode: "Connection Mode",
      userId: "User ID",
      apiKey: "API Key",
      library: "Library",
      username: "Username",
      token: "Personal Access Token",
      defaultOwner: "Default Owner",
      defaultBranch: "Default Branch",
      projectsRoot: "Projects Root",
      datasetRoot: "Dataset Root",
      experimentRoot: "Experiment Root",
      placeholderOnly: "Structure reserved for a later iteration.",
      saved: "Settings saved.",
    },
    focusMode: {
      title: "Focus Mode",
      currentTime: "Current Time",
      start: "Start Focus",
      pause: "Pause",
      resume: "Resume",
      finish: "Finish Focus",
      exit: "Exit Focus Mode",
      task: "Linked Task",
      project: "Linked Project",
      noTask: "No linked task",
      noProject: "No linked project",
      noAssociation: "No Association",
      note: "Note",
      elapsed: "Current Session",
      today: "Today Total",
      week: "Week Total",
      running: "Focusing",
      paused: "Paused",
    },

  },
};

export default function App() {
  const [tab, setTab] = useState<Tab>("dashboard");
  const [lang, setLang] = useState<Lang>(() => (localStorage.getItem("rrw-lang") === "en" ? "en" : "zh"));
  const [summary, setSummary] = useState<Summary | null>(null);
  const [dashboardSummary, setDashboardSummary] = useState<DashboardSummary | null>(null);
  const [settings, setSettings] = useState<SystemSettings | null>(null);
  const [focusMode, setFocusMode] = useState(false);
  const [projects, setProjects] = useState<Project[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [papers, setPapers] = useState<Paper[]>([]);
  const [notes, setNotes] = useState<ReadingNote[]>([]);
  const [experiments, setExperiments] = useState<Experiment[]>([]);
  const [knowledge, setKnowledge] = useState<KnowledgeLink[]>([]);
  const [message, setMessage] = useState<string>(ui[lang].connecting);
  const [loading, setLoading] = useState(false);
  const t = ui[lang];

  async function switchLanguage() {
    const next = lang === "zh" ? "en" : "zh";
    setLang(next);
    localStorage.setItem("rrw-lang", next);
    if (settings) {
      const updated = { ...settings, general: { language: next === "zh" ? "zh-CN" : "en-US" } };
      const saved = await api.updateSettings(updated);
      setSettings(saved);
    }
    setMessage(ui[next].connected);
  }

  async function refresh() {
    try {
      const [summaryData, dashboardData, settingsData, projectData, taskData, paperData, noteData, experimentData, knowledgeData] = await Promise.all([
        api.summary(),
        api.dashboardSummary(),
        api.settings(),
        api.projects(),
        api.tasks(),
        api.papers(),
        api.notes(),
        api.experiments(),
        api.knowledge(),
      ]);
      setSummary(summaryData);
      setDashboardSummary(dashboardData);
      setSettings(settingsData);
      const backendLang = settingsData.general.language === "en-US" ? "en" : "zh";
      if (backendLang !== lang) {
        setLang(backendLang);
        localStorage.setItem("rrw-lang", backendLang);
      }
      setProjects(projectData);
      setTasks(taskData);
      setPapers(paperData);
      setNotes(noteData);
      setExperiments(experimentData);
      setKnowledge(knowledgeData);
      setMessage(ui[backendLang].connected);
    } catch (error) {
      setMessage(`${t.backendOffline}: ${friendlyError(error)}`);
    }
  }

  useEffect(() => {
    void refresh();
  }, [lang]);

  const nav: Array<[Tab, typeof LayoutDashboard, string]> = [
    ["dashboard", LayoutDashboard, t.nav.dashboard],
    ["study", CalendarDays, t.nav.study],
    ["projects", Boxes, t.nav.projects],
    ["papers", BookOpen, t.nav.papers],
    ["knowledge", Link, t.nav.knowledge],
    ["research", PenLine, t.nav.research],
    ["review", BarChart3, t.nav.review],
    ["notes", NotebookPen, t.nav.notes],
    ["experiments", FlaskConical, t.nav.experiments],
    ["settings", SettingsIcon, t.nav.settings],
  ];

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">RR</div>
          <div>
            <strong>RoboResearch</strong>
            <span>{t.subtitle}</span>
          </div>
        </div>
        <nav>
          {nav.map(([key, Icon, label]) => (
            <button key={key} className={tab === key ? "active" : ""} onClick={() => setTab(key)}>
              <Icon size={18} />
              {label}
            </button>
          ))}
        </nav>
        <div className="status">
          <ShieldCheck size={16} />
          <span>{message}</span>
        </div>
        <button className="language-toggle" onClick={switchLanguage} title="Language">
          <Languages size={17} />
          {lang === "zh" ? "中文" : "English"}
        </button>
      </aside>

      <main>
        <header className="topbar">
          <div>
            <h1>{nav.find(([key]) => key === tab)?.[2]}</h1>
            <p>{t.tagline}</p>
          </div>
          <button className="primary" onClick={() => void refresh()} disabled={loading || focusMode}>
            {loading ? <Loader2 size={16} className="spin" /> : <Check size={16} />}
            {t.refresh}
          </button>
        </header>

        {tab === "dashboard" && (focusMode ? <FocusMode t={t.focusMode} tasks={tasks} projects={projects} summary={dashboardSummary} refresh={refresh} exit={() => setFocusMode(false)} /> : <Dashboard t={t.dashboard} summary={dashboardSummary} tasks={tasks} refresh={refresh} openFocus={() => setFocusMode(true)} setTab={setTab} />)}
        {tab === "study" && <StudyLife t={t.study} tasks={tasks} refresh={refresh} />}
        {tab === "projects" && <Projects t={t.projects} projects={projects} refresh={refresh} />}
        {tab === "papers" && <Papers t={t.papers} papers={papers} refresh={refresh} setMessage={setMessage} setLoading={setLoading} />}
        {tab === "knowledge" && <Knowledge t={t.knowledge} knowledge={knowledge} refresh={refresh} />}
        {tab === "research" && <ResearchWriting t={t.research} projects={projects} papers={papers} notes={notes} experiments={experiments} />}
        {tab === "review" && <Review t={t.review} moduleRows={coreModuleRows[lang]} summary={summary} projects={projects} papers={papers} experiments={experiments} />}
        {tab === "notes" && <Notes t={t.notes} notes={notes} papers={papers} refresh={refresh} />}
        {tab === "experiments" && <Experiments t={t.experiments} experiments={experiments} projects={projects} refresh={refresh} />}
        {tab === "settings" && settings && <SettingsPage t={t.settings} settings={settings} setSettings={setSettings} setLang={setLang} setMessage={setMessage} />}
      </main>
    </div>
  );
}



function Dashboard({ t, summary, tasks, refresh, openFocus, setTab }: {
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



function FocusMode({ t, tasks, projects, summary, refresh, exit }: {
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

function SettingsPage({ t, settings, setSettings, setLang, setMessage }: {
  t: typeof ui.zh.settings;
  settings: SystemSettings;
  setSettings: (settings: SystemSettings) => void;
  setLang: (lang: Lang) => void;
  setMessage: (message: string) => void;
}) {
  const [draft, setDraft] = useState<SystemSettings>(settings);

  useEffect(() => setDraft(settings), [settings]);

  async function save(nextDraft = draft) {
    const saved = await api.updateSettings(nextDraft);
    setSettings(saved);
    const nextLang = saved.general.language === "en-US" ? "en" : "zh";
    setLang(nextLang);
    localStorage.setItem("rrw-lang", nextLang);
    setMessage(t.saved);
  }

  async function test(integration: string) {
    const result = await api.testSettings(integration);
    setMessage(result.message);
  }

  function update<K extends keyof SystemSettings>(section: K, value: SystemSettings[K]) {
    setDraft((current) => ({ ...current, [section]: value }));
  }

  const integrations = draft.integrations;
  return (
    <section className="settings-layout">
      <div className="panel accent-cyan">
        <h2>{t.general}</h2>
        <label className="field-label"><span>{t.language}</span>
          <select value={draft.general.language} onChange={(event) => {
            const next = { ...draft, general: { language: event.target.value } };
            setDraft(next);
            void save(next);
          }}>
            <option value="zh-CN">{t.chinese}</option>
            <option value="en-US">{t.english}</option>
          </select>
        </label>
      </div>

      <div className="panel accent-green settings-wide">
        <div className="panel-heading compact-heading"><h2>{t.paths}</h2><button onClick={() => void test("paths")}>{t.test}</button></div>
        <div className="settings-grid">
          <PathInput label={t.projectsRoot} value={draft.paths.projects_root} onChange={(value) => update("paths", { ...draft.paths, projects_root: value })} />
          <PathInput label={t.knowledgeRoot} value={draft.paths.knowledge_root} onChange={(value) => update("paths", { ...draft.paths, knowledge_root: value })} />
          <PathInput label={t.vaultPath} value={draft.paths.obsidian_vault} onChange={(value) => update("paths", { ...draft.paths, obsidian_vault: value })} />
          <PathInput label={t.datasetRoot} value={draft.paths.dataset_root} onChange={(value) => update("paths", { ...draft.paths, dataset_root: value })} />
          <PathInput label={t.experimentRoot} value={draft.paths.experiment_root} onChange={(value) => update("paths", { ...draft.paths, experiment_root: value })} />
        </div>
      </div>

      <div className="panel accent-violet settings-wide">
        <h2>{t.integrations}</h2>
        <div className="integration-grid">
          <IntegrationPanel title={t.obsidian} enabled={integrations.obsidian.enabled} onEnabled={(enabled) => update("integrations", { ...integrations, obsidian: { ...integrations.obsidian, enabled } })} onTest={() => void test("obsidian")} testLabel={t.test} enabledLabel={t.enabled}>
            <PathInput label={t.vaultPath} value={integrations.obsidian.vault_path} onChange={(value) => update("integrations", { ...integrations, obsidian: { ...integrations.obsidian, vault_path: value } })} />
            <PathInput label={t.knowledgeRoot} value={integrations.obsidian.knowledge_root} onChange={(value) => update("integrations", { ...integrations, obsidian: { ...integrations.obsidian, knowledge_root: value } })} />
            <label className="checkbox-line"><input type="checkbox" checked={integrations.obsidian.use_obsidian_uri} onChange={(event) => update("integrations", { ...integrations, obsidian: { ...integrations.obsidian, use_obsidian_uri: event.target.checked } })} />{t.useObsidianUri}</label>
          </IntegrationPanel>

          <IntegrationPanel title={t.zotero} enabled={integrations.zotero.enabled} onEnabled={(enabled) => update("integrations", { ...integrations, zotero: { ...integrations.zotero, enabled } })} onTest={() => void test("zotero")} testLabel={t.test} enabledLabel={t.enabled}>
            <PathInput label={t.connectionMode} value={integrations.zotero.connection_mode} onChange={(value) => update("integrations", { ...integrations, zotero: { ...integrations.zotero, connection_mode: value } })} />
            <PathInput label={t.userId} value={integrations.zotero.user_id} onChange={(value) => update("integrations", { ...integrations, zotero: { ...integrations.zotero, user_id: value } })} />
            <PathInput label={t.apiKey} value={integrations.zotero.api_key ?? integrations.zotero.api_key_masked ?? ""} onChange={(value) => update("integrations", { ...integrations, zotero: { ...integrations.zotero, api_key: value } })} password />
            <PathInput label={t.library} value={integrations.zotero.library} onChange={(value) => update("integrations", { ...integrations, zotero: { ...integrations.zotero, library: value } })} />
          </IntegrationPanel>

          <IntegrationPanel title={t.github} enabled={integrations.github.enabled} onEnabled={(enabled) => update("integrations", { ...integrations, github: { ...integrations.github, enabled } })} onTest={() => void test("github")} testLabel={t.test} enabledLabel={t.enabled}>
            <PathInput label={t.username} value={integrations.github.username} onChange={(value) => update("integrations", { ...integrations, github: { ...integrations.github, username: value } })} />
            <PathInput label={t.token} value={integrations.github.personal_access_token ?? integrations.github.personal_access_token_masked ?? ""} onChange={(value) => update("integrations", { ...integrations, github: { ...integrations.github, personal_access_token: value } })} password />
            <PathInput label={t.defaultOwner} value={integrations.github.default_owner} onChange={(value) => update("integrations", { ...integrations, github: { ...integrations.github, default_owner: value } })} />
            <PathInput label={t.defaultBranch} value={integrations.github.default_branch} onChange={(value) => update("integrations", { ...integrations, github: { ...integrations.github, default_branch: value } })} />
          </IntegrationPanel>
        </div>
        <button className="primary settings-save" onClick={() => void save()}><Check size={16} />{t.save}</button>
      </div>

      <div className="panel accent-amber"><h2>{t.appearance}</h2><p className="muted">{t.placeholderOnly}</p></div>
      <div className="panel accent-rose"><h2>{t.advanced}</h2><p className="muted">{t.placeholderOnly}</p></div>
    </section>
  );
}

function PathInput({ label, value, onChange, password = false }: { label: string; value: string; onChange: (value: string) => void; password?: boolean }) {
  return <label className="field-label"><span>{label}</span><input type={password ? "password" : "text"} value={value} onChange={(event) => onChange(event.target.value)} /></label>;
}

function IntegrationPanel({ title, enabled, onEnabled, onTest, testLabel, enabledLabel, children }: {
  title: string;
  enabled: boolean;
  onEnabled: (enabled: boolean) => void;
  onTest: () => void;
  testLabel: string;
  enabledLabel: string;
  children: ReactNode;
}) {
  return <article className="integration-panel">
    <div className="panel-heading compact-heading">
      <h3>{title}</h3>
      <button onClick={onTest}>{testLabel}</button>
    </div>
    <label className="checkbox-line"><input type="checkbox" checked={enabled} onChange={(event) => onEnabled(event.target.checked)} />{enabledLabel}</label>
    <div className="form-grid">{children}</div>
  </article>;
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

function Projects({ t: _t, projects, refresh }: { t: typeof ui.zh.projects; projects: Project[]; refresh: () => Promise<void> }) {
  const statuses = ["", "Planning", "Active", "Blocked", "Paused", "Completed", "Archived"];
  const [items, setItems] = useState<Project[]>(projects);
  const [selected, setSelected] = useState<Project | null>(projects[0] ?? null);
  const [detail, setDetail] = useState<any>(null);
  const [activeTab, setActiveTab] = useState("overview");
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [tag, setTag] = useState("");
  const [sort, setSort] = useState("updated");
  const [message, setMessage] = useState("");
  const [browser, setBrowser] = useState<DirectoryListing | null>(null);
  const [scan, setScan] = useState<ProjectScan | null>(null);
  const [registerMeta, setRegisterMeta] = useState({ name: "", description: "", status: "Active", progress_mode: "AUTO", tags: "" });
  const [checked, setChecked] = useState<string[]>([]);
  const [diff, setDiff] = useState("");
  const [commitMessage, setCommitMessage] = useState("");
  const [versions, setVersions] = useState<GitCommit[]>([]);
  const [selectedVersion, setSelectedVersion] = useState<any>(null);
  const [branchName, setBranchName] = useState("");
  const [publish, setPublish] = useState({ repository_name: "", description: "", visibility: "private", default_branch: "main", confirm_risks: false });
  const [securityScan, setSecurityScan] = useState<any>(null);
  const [stageDrafts, setStageDrafts] = useState<Record<number, { status: string; progress: number; weight: number }>>({});
  const [newStage, setNewStage] = useState({ title: "", status: "pending", progress: 0, weight: 1 });

  useEffect(() => setItems(projects), [projects]);
  useEffect(() => {
    if (!selected && items[0]) setSelected(items[0]);
  }, [items, selected]);
  useEffect(() => {
    if (selected) void loadDetail(selected.id);
  }, [selected?.id]);

  const statusCounts = useMemo(() => {
    const counts: Record<string, number> = { Total: items.length, Planning: 0, Active: 0, Blocked: 0, Paused: 0, Completed: 0, Archived: 0 };
    items.forEach((project) => { counts[project.status] = (counts[project.status] ?? 0) + 1; });
    return counts;
  }, [items]);

  async function loadFiltered() {
    const data = await api.projects({ search, status, tag, sort });
    setItems(data);
    setMessage(`已加载 ${data.length} 个项目。`);
  }

  async function loadDetail(id = selected?.id) {
    if (!id) return;
    const data = await api.projectDetail(id);
    setDetail(data);
    setSelected(data.project);
    setItems((current) => current.map((project) => project.id === data.project.id ? data.project : project));
    setStageDrafts(Object.fromEntries((data.progress?.stages || []).filter((stage: ProjectStage) => stage.id).map((stage: ProjectStage) => [stage.id, { status: stage.status, progress: stage.progress, weight: stage.weight }])));
    setChecked([]);
    setDiff("");
    setPublish((current) => ({ ...current, repository_name: data.project.name, description: data.project.description || "", default_branch: data.project.default_branch || data.git?.branch || "main" }));
    if (activeTab === "versions") await loadVersions(id);
  }

  async function openBrowser(path?: string) {
    const data = await api.directories(path);
    setBrowser(data);
    setScan(null);
  }

  async function scanFolder(path: string) {
    const data = await api.scanProject(path);
    setScan(data);
    setRegisterMeta({ name: data.name, description: data.description || "", status: "Active", progress_mode: "AUTO", tags: data.tags.join(", ") });
    setPublish((current) => ({ ...current, repository_name: data.name, description: data.description || "", default_branch: data.branch || "main" }));
  }

  async function registerScannedProject() {
    if (!scan) return;
    const project = await api.registerProject({ path: scan.path, ...registerMeta });
    setSelected(project);
    setMessage(`已注册 ${project.name}。`);
    setScan(null);
    await refresh();
    await loadDetail(project.id);
  }

  async function gitAction(action: () => Promise<any>, success: string) {
    if (!selected) return;
    try {
      const result = await action();
      setMessage(result.ok === false ? result.stderr || "操作失败。" : success);
      if (result.scan) setSecurityScan(result.scan);
      await loadDetail(selected.id);
    } catch (error) {
      setMessage(friendlyError(error));
    }
  }

  async function showDiff(path: string) {
    if (!selected) return;
    const result = await api.gitDiff(selected.id, path);
    setDiff(result.stdout || result.stderr || "没有差异。");
  }

  async function selectAllSafeChanges() {
    if (!selected || !git?.changes?.length) return;
    const scan = await api.prePushCheck(selected.id);
    setSecurityScan(scan);
    const safe = new Set((scan.safe_files || []) as string[]);
    const selectable = git.changes.map((change: any) => change.path).filter((path: string) => safe.has(path));
    setChecked(selectable);
    setMessage(scan.blocked_files?.length || scan.secret_matches?.length || scan.large_files?.length ? "已全选安全文件，有风险文件已保留为未选择。" : "已全选所有可提交文件。");
  }

  async function loadVersions(id = selected?.id) {
    if (!id) return;
    const data = await api.versions(id);
    setVersions(data);
  }

  async function selectVersion(commit: GitCommit) {
    if (!selected) return;
    const data = await api.versionDetail(selected.id, commit.hash);
    setSelectedVersion(data);
  }

  async function publishToGithub(confirm = false) {
    if (!selected) return;
    try {
      const result = await api.publishGithub(selected.id, { ...publish, confirm_risks: confirm || publish.confirm_risks });
      if (result.requires_confirmation) {
        setSecurityScan(result.scan);
        setMessage("发布前需要先查看安全检查结果。");
        return;
      }
      setSecurityScan(result.scan);
      setMessage(result.ok ? "已发布到 GitHub。" : result.push?.stderr || result.stderr || "发布失败。");
      await refresh();
      await loadDetail(selected.id);
    } catch (error) {
      setMessage(`发布失败：${friendlyError(error)}`);
    }
  }

  async function saveProjectSettings() {
    if (!selected || !detail?.project) return;
    const updated = await api.updateProject(selected.id, detail.project);
    setSelected(updated);
    setDetail((current: any) => current ? { ...current, project: updated } : current);
    setItems((current) => current.map((project) => project.id === updated.id ? updated : project));
    await refresh();
    await loadDetail(updated.id);
    setMessage("项目设置已保存。");
  }

  async function saveStage(stage: ProjectStage) {
    if (!stage.id || !selected) return;
    await api.updateStage(stage.id, stageDrafts[stage.id]);
    setMessage("阶段已更新。");
    await loadDetail(selected.id);
    await refresh();
  }

  async function initializeDefaultStages() {
    if (!selected) return;
    const data = await api.initializeProjectProgress(selected.id);
    setDetail((current: any) => ({ ...(current || {}), ...data }));
    setSelected(data.project);
    setItems((current) => current.map((project) => project.id === data.project.id ? data.project : project));
    setStageDrafts(Object.fromEntries((data.progress?.stages || []).filter((stage: ProjectStage) => stage.id).map((stage: ProjectStage) => [stage.id, { status: stage.status, progress: stage.progress, weight: stage.weight }])));
    setMessage("已初始化默认阶段。");
  }

  async function createCustomStage() {
    if (!selected || !newStage.title.trim()) return;
    await api.createStage({
      project_id: selected.id,
      title: newStage.title.trim(),
      status: newStage.status,
      progress: newStage.progress,
      weight: newStage.weight,
      order_index: progress?.stages?.length ?? 0,
    });
    setNewStage({ title: "", status: "pending", progress: 0, weight: 1 });
    await loadDetail(selected.id);
    await refresh();
    setMessage("阶段已添加。");
  }

  const git = detail?.git;
  const progress: ProjectProgress | undefined = detail?.progress;
  const selectedProject = detail?.project as Project | undefined;

  return (
    <section className="projects-hub">
      <div className="panel project-sidebar">
        <div className="section-head">
          <h2>项目中心</h2>
          <button className="primary" onClick={() => void openBrowser()}><FolderOpen size={16} />注册本地项目</button>
        </div>
        <div className="stats-grid compact-stats">
          {Object.entries(statusCounts).map(([key, value]) => <Metric key={key} label={projectStatusText(key)} value={Number(value)} />)}
        </div>
        <div className="form-grid filters">
          <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="搜索项目" />
          <select value={status} onChange={(event) => setStatus(event.target.value)}>{statuses.map((item) => <option key={item || "all"} value={item}>{item ? projectStatusText(item) : "全部状态"}</option>)}</select>
          <input value={tag} onChange={(event) => setTag(event.target.value)} placeholder="Tag" />
          <select value={sort} onChange={(event) => setSort(event.target.value)}><option value="updated">最近更新</option><option value="name">名称</option><option value="progress">进度</option></select>
          <button onClick={() => void loadFiltered()}><SlidersHorizontal size={16} />应用</button>
        </div>
        <div className="project-list">
          {items.map((project) => <ProjectCard key={project.id} project={project} selected={selected?.id === project.id} onClick={() => setSelected(project)} />)}
        </div>
      </div>

      <div className="panel project-main">
        {browser && (
          <div className="folder-picker">
            <div className="section-head">
              <div>
                <h2>选择项目文件夹</h2>
                <p className="muted">当前使用后端目录浏览器选择真实本地路径；后续接入 Tauri 后可替换为系统原生文件夹选择器。</p>
              </div>
              <button onClick={() => setBrowser(null)}>关闭</button>
            </div>
            <div className="pathbar">
              {browser.parent && <button onClick={() => void openBrowser(browser.parent || undefined)}><ChevronLeft size={16} />上一级</button>}
              <code>{browser.path}</code>
              <button className="primary" onClick={() => void scanFolder(browser.path)}><Search size={16} />扫描此文件夹</button>
            </div>
            <div className="folder-grid">
              {browser.items.map((item) => <button key={item.path} onClick={() => void openBrowser(item.path)}><FolderOpen size={16} />{item.name}</button>)}
            </div>
          </div>
        )}

        {scan && (
          <div className="scan-preview">
            <h2>注册预览</h2>
            <div className="metric-row three">
              <Metric label="类型" value={registrationCaseText(scan.registration_case)} />
              <Metric label="项目类型" value={scan.project_type} />
              <Metric label="分支" value={scan.branch || "无"} />
            </div>
            <div className="tag-cloud">{Object.entries(scan.detections).map(([key, value]) => <span key={key}>{value ? "✓" : "-"} {detectionLabels[key] || key}</span>)}</div>
            <div className="form-grid settings-grid">
              <input value={registerMeta.name} onChange={(event) => setRegisterMeta({ ...registerMeta, name: event.target.value })} placeholder="项目名称" />
              <select value={registerMeta.status} onChange={(event) => setRegisterMeta({ ...registerMeta, status: event.target.value })}>{statuses.filter(Boolean).map((item) => <option key={item} value={item}>{projectStatusText(item)}</option>)}</select>
              <select value={registerMeta.progress_mode} onChange={(event) => setRegisterMeta({ ...registerMeta, progress_mode: event.target.value })}><option value="AUTO">自动计算进度</option><option value="MANUAL">手动设置进度</option></select>
              <input value={registerMeta.tags} onChange={(event) => setRegisterMeta({ ...registerMeta, tags: event.target.value })} placeholder="标签" />
              <textarea value={registerMeta.description} onChange={(event) => setRegisterMeta({ ...registerMeta, description: event.target.value })} placeholder="项目描述" />
              <button className="primary" onClick={() => void registerScannedProject()}><Save size={16} />确认注册</button>
            </div>
          </div>
        )}

        {!selectedProject && !browser && <p className="muted">请选择或注册一个项目，用于管理本地进度、Git、GitHub 与版本历史。</p>}
        {selectedProject && (
          <>
            <div className="project-hero">
              <div>
                <span className={`status-pill ${selectedProject.status.toLowerCase()}`}>{projectStatusText(selectedProject.status)}</span>
                <h2>{selectedProject.name}</h2>
                <p>{selectedProject.description || selectedProject.path}</p>
              </div>
              <div className="hero-actions">
                <button onClick={() => void loadDetail(selectedProject.id)}><RefreshCw size={16} />刷新</button>
                {selectedProject.remote_url && <a href={githubWebUrl(selectedProject.remote_url)} target="_blank"><Link size={16} />打开 GitHub</a>}
              </div>
            </div>
            <div className="tabs project-tabs">{["overview", "progress", "git", "versions", "settings"].map((item) => <button key={item} className={activeTab === item ? "active-pill" : ""} onClick={() => { setActiveTab(item); if (item === "versions") void loadVersions(selectedProject.id); }}>{projectTabLabels[item]}</button>)}</div>

            {activeTab === "overview" && (
              <div className="detail-grid">
                <div className="panel-lite">
                  <h3>项目状态</h3>
                  <ProgressLine label="进度" value={progress?.progress ?? selectedProject.progress} />
                  <div className="metric-row three"><Metric label="当前阶段" value={selectedProject.current_stage || "未设置"} /><Metric label="下一阶段" value={selectedProject.next_stage || "未设置"} /><Metric label="健康状态" value={healthText(selectedProject.health)} /></div>
                </div>
                <div className="panel-lite">
                  <h3>本地与 Git</h3>
                  <div className="kv"><span>路径</span><code>{selectedProject.path}</code></div>
                  <div className="kv"><span>Git</span><strong>{git?.is_repo ? "已初始化" : "未初始化"}</strong></div>
                  <div className="kv"><span>Remote</span><strong>{git?.remote_url ? "已连接" : "无"}</strong></div>
                  <div className="kv"><span>Branch</span><strong>{git?.branch || "无"}</strong></div>
                </div>
                <div className="panel-lite">
                  <h3>研究关联</h3>
                  <div className="record"><strong>最近实验</strong><span>{detail?.experiments?.length ? detail.experiments.map((item: Experiment) => item.code).join(", ") : "暂无关联实验"}</span></div>
                  <div className="record"><strong>关键版本</strong><span>{detail?.checkpoints?.length || 0}</span></div>
                </div>
              </div>
            )}

            {activeTab === "progress" && progress && (
              <div className="stack">
                <div className="panel-lite progress-summary-panel">
                  <div className="section-head">
                    <div>
                      <h3>进度总览</h3>
                      <p className="muted">总进度来自阶段、里程碑和任务；当前阶段和下一阶段是项目设置里的手动说明。</p>
                    </div>
                    <button onClick={() => void initializeDefaultStages()}>初始化默认阶段</button>
                  </div>
                  <ProgressLine label="项目总进度" value={progress.progress} />
                  <div className="metric-row three">
                    <Metric label="进度模式" value={progress.mode === "MANUAL" ? "手动" : "自动"} />
                    <Metric label="阶段数量" value={progress.stages.length} />
                    <Metric label="自动识别当前阶段" value={progress.computed_current_stage || "无"} />
                  </div>
                  <div className="metric-row three">
                    <Metric label="当前阶段说明" value={selectedProject.current_stage || "未设置"} />
                    <Metric label="下一阶段说明" value={selectedProject.next_stage || "未设置"} />
                    <Metric label="健康状态" value={healthText(selectedProject.health)} />
                  </div>
                </div>

                <div className="panel-lite">
                  <div className="section-head">
                    <div>
                      <h3>阶段时间线</h3>
                      <p className="muted">在这里维护阶段完成度；如果使用自动模式，项目总进度会按阶段权重计算。</p>
                    </div>
                  </div>
                  {progress.stages.length === 0 && (
                    <div className="empty-state">
                      <strong>还没有阶段数据</strong>
                      <span>可以初始化默认阶段，也可以在下方手动添加第一个阶段。</span>
                    </div>
                  )}
                  {progress.stages.map((stage) => {
                    const draft = stage.id ? stageDrafts[stage.id] : undefined;
                    return (
                      <div className="stage-card" key={stage.id || stage.title}>
                        <div className="stage-title-row">
                          <strong>{stage.title}</strong>
                          <span className={`stage-status ${stage.status}`}>{stageStatusText(stage.status)}</span>
                        </div>
                        <ProgressLine label="阶段进度" value={stage.progress} />
                        <div className="stage-edit-row">
                          <select value={draft?.status || stage.status} onChange={(event) => stage.id && setStageDrafts((items) => ({ ...items, [stage.id!]: { ...(items[stage.id!] || { progress: stage.progress, weight: stage.weight, status: stage.status }), status: event.target.value } }))}>
                            <option value="pending">待开始</option>
                            <option value="active">进行中</option>
                            <option value="completed">已完成</option>
                            <option value="blocked">阻塞</option>
                          </select>
                          <input type="number" min="0" max="100" value={draft?.progress ?? stage.progress} onChange={(event) => stage.id && setStageDrafts((items) => ({ ...items, [stage.id!]: { ...(items[stage.id!] || { progress: stage.progress, weight: stage.weight, status: stage.status }), progress: Number(event.target.value) } }))} />
                          <input type="number" min="0" step="0.5" value={draft?.weight ?? stage.weight} onChange={(event) => stage.id && setStageDrafts((items) => ({ ...items, [stage.id!]: { ...(items[stage.id!] || { progress: stage.progress, weight: stage.weight, status: stage.status }), weight: Number(event.target.value) } }))} />
                          <button disabled={!stage.id} onClick={() => void saveStage(stage)}>保存阶段</button>
                        </div>
                        {stage.milestones?.length ? stage.milestones.map((milestone) => <div className="milestone-row" key={milestone.id}><span>{milestone.title}</span><progress value={milestone.progress} max={100} /><strong>{Math.round(milestone.progress)}%</strong></div>) : <p className="muted">暂无里程碑，当前阶段进度使用阶段本身的进度值。</p>}
                      </div>
                    );
                  })}
                  <div className="stage-create-row">
                    <input value={newStage.title} onChange={(event) => setNewStage({ ...newStage, title: event.target.value })} placeholder="新增阶段名称，例如：真实机器人测试" />
                    <select value={newStage.status} onChange={(event) => setNewStage({ ...newStage, status: event.target.value })}>
                      <option value="pending">待开始</option>
                      <option value="active">进行中</option>
                      <option value="completed">已完成</option>
                      <option value="blocked">阻塞</option>
                    </select>
                    <input type="number" min="0" max="100" value={newStage.progress} onChange={(event) => setNewStage({ ...newStage, progress: Number(event.target.value) })} />
                    <input type="number" min="0" step="0.5" value={newStage.weight} onChange={(event) => setNewStage({ ...newStage, weight: Number(event.target.value) })} />
                    <button className="primary" disabled={!newStage.title.trim()} onClick={() => void createCustomStage()}><Plus size={16} />添加阶段</button>
                  </div>
                </div>
              </div>
            )}


            {activeTab === "git" && (
              <div className="git-layout">
                <div className="panel-lite">
                  <h3>仓库状态</h3>
                  <div className="metric-row three"><Metric label="分支" value={git?.branch || "无"} /><Metric label="已修改" value={git?.modified ?? 0} /><Metric label="未跟踪" value={git?.untracked ?? 0} /></div>
                  <div className="toolbar"><button onClick={() => void gitAction(() => api.gitInit(selectedProject.id), "Git 已初始化。")}><GitBranch size={16} />初始化 Git</button><button onClick={() => void gitAction(() => api.gitPull(selectedProject.id, git?.branch || undefined), "拉取完成。") }><RefreshCw size={16} />拉取</button><button onClick={() => void gitAction(() => api.gitPush(selectedProject.id, git?.branch), "推送完成。") }><Send size={16} />推送</button><button onClick={() => void api.prePushCheck(selectedProject.id).then(setSecurityScan)}><ShieldCheck size={16} />安全检查</button></div>
                  <div className="toolbar"><button disabled={!git?.changes?.length} onClick={() => void selectAllSafeChanges()}>全选安全文件</button><button disabled={!checked.length} onClick={() => setChecked([])}>清空选择</button><span className="muted">已选择 {checked.length} / {git?.changes?.length || 0}</span></div>
                  <div className="changes">{git?.changes?.map((change: any) => <label key={change.path}><input type="checkbox" checked={checked.includes(change.path)} onChange={(event) => setChecked((items) => event.target.checked ? Array.from(new Set([...items, change.path])) : items.filter((item) => item !== change.path))} /><code>{change.status}</code><button className="link-button" onClick={() => void showDiff(change.path)}>{change.path}</button></label>)}</div>
                  <div className="toolbar"><button disabled={!checked.length} onClick={() => void gitAction(() => api.gitStage(selectedProject.id, checked), "文件已暂存。")}>暂存</button><button disabled={!checked.length} onClick={() => void gitAction(() => api.gitUnstage(selectedProject.id, checked), "文件已取消暂存。")}>取消暂存</button></div>
                  <div className="form-grid"><input value={commitMessage} onChange={(event) => setCommitMessage(event.target.value)} placeholder="提交信息" /><button className="primary" disabled={!checked.length || commitMessage.length < 3} onClick={() => void gitAction(() => api.gitCommit(selectedProject.id, checked, commitMessage), "提交已创建。")}><GitCommitHorizontal size={16} />提交所选文件</button></div>
                </div>
                <div className="panel-lite"><h3>差异</h3><pre className="diff-box">{diff || "选择一个变更文件查看差异。"}</pre><h3>发布到 GitHub</h3><div className="form-grid"><input value={publish.repository_name} onChange={(event) => setPublish({ ...publish, repository_name: event.target.value })} placeholder="仓库名称" /><input value={publish.description} onChange={(event) => setPublish({ ...publish, description: event.target.value })} placeholder="项目描述" /><select value={publish.visibility} onChange={(event) => setPublish({ ...publish, visibility: event.target.value })}><option value="private">私有</option><option value="public">公开</option></select><input value={publish.default_branch} onChange={(event) => setPublish({ ...publish, default_branch: event.target.value })} placeholder="默认分支" /><button className="primary" onClick={() => void publishToGithub(false)}><UploadCloud size={16} />创建仓库并推送</button>{securityScan && <SecurityScan scan={securityScan} onContinue={() => void publishToGithub(true)} />}</div></div>
              </div>
            )}

            {activeTab === "versions" && (
              <div className="versions-layout">
                <div className="panel-lite"><div className="section-head"><h3>提交历史</h3><button onClick={() => void loadVersions(selectedProject.id)}><History size={16} />加载</button></div><div className="version-list">{versions.map((commit) => <button key={commit.hash} className="version-item" onClick={() => void selectVersion(commit)}><strong>{commit.short_hash} {commit.message}</strong><span>{commit.author} · {commit.date}</span><small>{commit.stats}</small></button>)}</div></div>
                <div className="panel-lite"><h3>版本详情</h3>{selectedVersion ? <><div className="record"><strong>{selectedVersion.short_hash} {selectedVersion.message}</strong><span>{selectedVersion.author} · {selectedVersion.date}</span></div><div className="toolbar"><button onClick={() => void gitAction(() => api.openVersion(selectedProject.id, selectedVersion.hash), "历史版本已作为 worktree 打开。")}><Eye size={16} />打开此版本</button><input value={branchName} onChange={(event) => setBranchName(event.target.value)} placeholder="recovery/branch-name" /><button disabled={!branchName} onClick={() => void gitAction(() => api.createBranchFromVersion(selectedProject.id, selectedVersion.hash, branchName), "分支已创建。")}><GitBranch size={16} />创建分支</button><button className="danger" onClick={() => { if (window.confirm("恢复会重写当前分支；如果存在未提交修改，系统会自动阻止。确认继续？")) void gitAction(() => api.restoreVersion(selectedProject.id, selectedVersion.hash, true), "项目已恢复，并已创建备份分支。"); }}><RotateCcw size={16} />恢复项目到此版本</button></div><pre className="diff-box">{selectedVersion.diff}</pre></> : <p className="muted">选择一个提交后，可以查看详情、以 worktree 打开、创建分支或安全恢复。</p>}</div>
              </div>
            )}

            {activeTab === "settings" && selectedProject && (
              <div className="panel-lite">
                <h3>项目设置</h3>
                <div className="form-grid settings-grid">
                  <label><span>项目名称</span><input value={detail.project.name || ""} onChange={(event) => setDetail({ ...detail, project: { ...detail.project, name: event.target.value } })} /></label>
                  <label><span>项目状态</span><select value={detail.project.status || "Active"} onChange={(event) => setDetail({ ...detail, project: { ...detail.project, status: event.target.value } })}>{statuses.filter(Boolean).map((item) => <option key={item} value={item}>{projectStatusText(item)}</option>)}</select></label>
                  <label><span>当前阶段</span><input value={detail.project.current_stage || ""} onChange={(event) => setDetail({ ...detail, project: { ...detail.project, current_stage: event.target.value } })} placeholder="例如：Baseline 复现" /></label>
                  <label><span>下一阶段</span><input value={detail.project.next_stage || ""} onChange={(event) => setDetail({ ...detail, project: { ...detail.project, next_stage: event.target.value } })} placeholder="例如：真实机器人测试" /></label>
                  <label><span>进度模式</span><select value={detail.project.progress_mode || "AUTO"} onChange={(event) => setDetail({ ...detail, project: { ...detail.project, progress_mode: event.target.value } })}><option value="AUTO">自动计算进度</option><option value="MANUAL">手动设置进度</option></select></label>
                  <label><span>手动总进度</span><input type="number" min="0" max="100" value={detail.project.progress || 0} onChange={(event) => setDetail({ ...detail, project: { ...detail.project, progress: Number(event.target.value) } })} disabled={detail.project.progress_mode !== "MANUAL"} /></label>
                  <label><span>默认分支</span><input value={detail.project.default_branch || ""} onChange={(event) => setDetail({ ...detail, project: { ...detail.project, default_branch: event.target.value } })} placeholder="默认分支" /></label>
                  <label><span>实验目录</span><input value={detail.project.experiment_dir || ""} onChange={(event) => setDetail({ ...detail, project: { ...detail.project, experiment_dir: event.target.value } })} placeholder="实验目录" /></label>
                  <label><span>结果目录</span><input value={detail.project.results_dir || ""} onChange={(event) => setDetail({ ...detail, project: { ...detail.project, results_dir: event.target.value } })} placeholder="结果目录" /></label>
                  <label className="full-field"><span>项目描述</span><textarea value={detail.project.description || ""} onChange={(event) => setDetail({ ...detail, project: { ...detail.project, description: event.target.value } })} /></label>
                  <button className="primary" onClick={() => void saveProjectSettings()}><SettingsIcon size={16} />保存项目设置</button>
                </div>
              </div>
            )}
          </>
        )}
        {message && <p className="notice">{message}</p>}
      </div>
    </section>
  );
}

function ProjectCard({ project, selected, onClick }: { project: Project; selected: boolean; onClick: () => void }) {
  return <button className={`project-card-row ${selected ? "selected" : ""}`} onClick={onClick}><div><strong>{project.name}</strong><span>{project.description || project.project_type || project.path}</span></div><span className={`status-pill ${project.status.toLowerCase()}`}>{projectStatusText(project.status)}</span><ProgressLine label={project.current_stage || "未设置当前阶段"} value={project.progress} /><div className="project-meta"><span>{project.path ? "本地 ✓" : "本地 -"}</span><span>{project.branch ? `Git ${project.branch}` : "Git -"}</span><span>{project.remote_url ? "GitHub ✓" : "GitHub -"}</span><span>{healthText(project.health)}</span></div></button>;
}

function SecurityScan({ scan, onContinue }: { scan: any; onContinue: () => void }) {
  const hasRisk = Boolean(scan?.blocked_files?.length || scan?.secret_matches?.length || scan?.large_files?.length);
  return <div className={`security-box ${hasRisk ? "risk" : ""}`}><div className="widget-title">{hasRisk ? <AlertTriangle size={16} /> : <ShieldCheck size={16} />}<strong>推送前安全检查</strong></div><p>安全文件： {scan?.safe_files?.length ?? 0}</p>{scan?.blocked_files?.length > 0 && <p>已拦截： {scan.blocked_files.slice(0, 8).join(", ")}</p>}{scan?.large_files?.length > 0 && <p>大文件： {scan.large_files.map((item: any) => item.path).slice(0, 5).join(", ")}</p>}{scan?.secret_matches?.length > 0 && <p>疑似密钥： {scan.secret_matches.map((item: any) => item.path).slice(0, 5).join(", ")}</p>}{hasRisk && <button onClick={onContinue}>仅使用安全文件继续</button>}</div>;
}

function Papers({ t, papers, refresh, setMessage, setLoading }: {
  t: typeof ui.zh.papers;
  papers: Paper[];
  refresh: () => Promise<void>;
  setMessage: (message: string) => void;
  setLoading: (value: boolean) => void;
}) {
  const [venue, setVenue] = useState("");
  const [query, setQuery] = useState("embodied intelligence robot task planning world model");
  const [keywords, setKeywords] = useState("VLA\nVLM\nworld model\nrobot task planning\nmanipulation");
  const [results, setResults] = useState<SearchPaper[]>([]);
  const [selected, setSelected] = useState<Record<string, SearchPaper>>({});

  const shown = venue ? papers.filter((paper) => paper.venue === venue) : papers;
  const chosen = Object.values(selected);

  async function search() {
    setLoading(true);
    try {
      const data = await api.searchPapers({
        query,
        sources: defaultSources,
        keywords: keywords.split(/\n|,/).map((item) => item.trim()).filter(Boolean),
        from_year: 2020,
        to_year: new Date().getFullYear(),
        per_source_limit: 20,
      });
      setResults(data.papers);
      setMessage(`${t.found} ${data.papers.length} ${t.foundSuffix}`);
    } catch (error) {
      setMessage(`${t.failed}: ${friendlyError(error)}`);
    } finally {
      setLoading(false);
    }
  }

  async function saveToWorkbench(paper: SearchPaper) {
    await api.savePaper({
      title: paper.title,
      translated_title: paper.translated_title,
      abstract: paper.abstract,
      translated_abstract: paper.translated_abstract,
      authors: paper.authors.join(", "),
      year: paper.year,
      venue: normalizeVenue(paper.source_label || paper.venue),
      tags: paper.matched_keywords.join(", "),
      doi: paper.doi,
      url: paper.url,
      pdf_url: paper.pdf_url,
      status: "inbox",
    });
    await refresh();
  }

  async function importZotero() {
    const result = await api.importZotero(chosen);
    setMessage(result.message ?? t.zoteroDone);
  }

  return (
    <section className="stack">
      <div className="panel">
        <h2>{t.searchTitle}</h2>
        <div className="form-grid paper-search">
          <input value={query} onChange={(event) => setQuery(event.target.value)} />
          <textarea value={keywords} onChange={(event) => setKeywords(event.target.value)} />
          <button className="primary" onClick={() => void search()}><Search size={16} />{t.search}</button>
          <button disabled={!chosen.length} onClick={() => void importZotero()}><Send size={16} />{t.importZotero}</button>
        </div>
      </div>
      <div className="panel">
        <h2>{t.saved}</h2>
        <div className="tabs">{["", ...venues].map((item) => <button key={item || "all"} className={venue === item ? "active-pill" : ""} onClick={() => setVenue(item)}>{item || t.all}</button>)}</div>
        <div className="paper-grid">{shown.map((paper) => <PaperCard key={paper.id} paper={paper} langText={{ noYear: t.noYear, open: t.open }} />)}</div>
      </div>
      <div className="panel">
        <h2>{t.results}</h2>
        <div className="paper-grid">
          {results.map((paper) => {
            const key = paper.doi || paper.id;
            return (
              <article className="paper-card" key={key}>
                <label className="select-row">
                  <input type="checkbox" checked={Boolean(selected[key])} onChange={(event) => {
                    setSelected((items) => {
                      const next = { ...items };
                      if (event.target.checked) next[key] = paper;
                      else delete next[key];
                      return next;
                    });
                  }} />
                  <span>{paper.source_label || paper.venue || t.unknown} · {paper.year || t.noYear}</span>
                </label>
                <h3>{paper.title}</h3>
                {paper.translated_title && <p className="muted">{paper.translated_title}</p>}
                <p>{paper.authors.slice(0, 6).join(", ")}</p>
                <div className="toolbar">
                  <button onClick={() => void saveToWorkbench(paper)}>{t.save}</button>
                  {paper.url && <a href={paper.url} target="_blank">{t.open}</a>}
                </div>
              </article>
            );
          })}
        </div>
      </div>
    </section>
  );
}

function Notes({ t, notes, papers, refresh }: { t: typeof ui.zh.notes; notes: ReadingNote[]; papers: Paper[]; refresh: () => Promise<void> }) {
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
        <h2>Preview</h2>
        <pre className="note-preview">{content}</pre>
      </div>
      <div className="panel accent-amber note-list-panel">
        <h2>{t.listTitle}</h2>
        <div className="list compact-cards">{notes.map((note) => <div className="list-card" key={note.id}><strong>{note.title}</strong><span>{note.status}</span><p>{note.content.slice(0, 260)}</p></div>)}</div>
      </div>
    </section>
  );
}

function Experiments({ t, experiments, projects, refresh }: { t: typeof ui.zh.experiments; experiments: Experiment[]; projects: Project[]; refresh: () => Promise<void> }) {
  const [form, setForm] = useState({ code: "EXP-001", title: t.defaultTitle, project_id: "", metrics: "success_rate=", result: "", conclusion: "" });
  async function create() {
    await api.createExperiment({ ...form, project_id: form.project_id ? Number(form.project_id) : null });
    await refresh();
  }
  return (
    <section className="page-grid">
      <div className="panel">
        <h2>{t.newTitle}</h2>
        <div className="form-grid">
          <input value={form.code} onChange={(event) => setForm({ ...form, code: event.target.value })} />
          <input value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} />
          <select value={form.project_id} onChange={(event) => setForm({ ...form, project_id: event.target.value })}>
            <option value="">{t.noProject}</option>
            {projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}
          </select>
          <textarea value={form.metrics} onChange={(event) => setForm({ ...form, metrics: event.target.value })} />
          <textarea value={form.result} onChange={(event) => setForm({ ...form, result: event.target.value })} placeholder={t.result} />
          <textarea value={form.conclusion} onChange={(event) => setForm({ ...form, conclusion: event.target.value })} placeholder={t.conclusion} />
          <button className="primary" onClick={() => void create()}><Plus size={16} />{t.create}</button>
        </div>
      </div>
      <div className="panel wide">
        <h2>{t.log}</h2>
        <div className="table">
          {experiments.map((experiment) => <div className="row" key={experiment.id}><strong>{experiment.code}</strong><span>{experiment.title}</span><span>{experiment.metrics}</span><span>{experiment.conclusion}</span></div>)}
        </div>
      </div>
    </section>
  );
}

function Knowledge({ t, knowledge, refresh }: { t: typeof ui.zh.knowledge; knowledge: KnowledgeLink[]; refresh: () => Promise<void> }) {
  const [form, setForm] = useState({ title: "VLA Action Representation", area: "Embodied AI", obsidian_uri: "", vault_path: "EmbodiedAI/VLA/Action-Representation.md", tags: "VLA,Action Tokenization" });
  async function create() {
    await api.createKnowledge(form);
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
      <div className="panel wide">
        <h2>{t.listTitle}</h2>
        <div className="paper-grid">{knowledge.map((item) => <article className="paper-card" key={item.id}><h3>{item.title}</h3><p>{item.area}</p><p>{item.vault_path}</p>{item.obsidian_uri && <a href={item.obsidian_uri}>{t.openObsidian}</a>}</article>)}</div>
      </div>
    </section>
  );
}


function StudyLife({ t, tasks, refresh }: { t: typeof ui.zh.study; tasks: Task[]; refresh: () => Promise<void> }) {
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
          {studyTasks.map((task) => <div className="list-card" key={task.id}><strong>{task.title}</strong><span>{task.priority} · {task.status}</span></div>)}
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

function ResearchWriting({ t, projects, papers, notes, experiments }: {
  t: typeof ui.zh.research;
  projects: Project[];
  papers: Paper[];
  notes: ReadingNote[];
  experiments: Experiment[];
}) {
  const pipeline = [t.ideas, "Hypothesis", "Baseline", t.figures, t.relatedWork, t.draft, t.revision, t.submission];
  return (
    <section className="dense-grid research-layout">
      <div className="panel wide accent-violet">
        <h2>{t.pipeline}</h2>
        <div className="pipeline">
          {pipeline.map((item, index) => <div key={item}><span>{String(index + 1).padStart(2, "0")}</span><strong>{item}</strong></div>)}
        </div>
      </div>
      <div className="panel accent-rose">
        <h2>{t.ideas}</h2>
        <ul className="compact-list">{t.ideaItems.map((item) => <li key={item}>{item}</li>)}</ul>
      </div>
      <div className="panel accent-amber">
        <h2>{t.figures}</h2>
        <ul className="compact-list">{t.figureItems.map((item) => <li key={item}>{item}</li>)}</ul>
      </div>
      <div className="panel accent-green">
        <h2>{t.writingBoard}</h2>
        <div className="metric-row triple">
          <Metric label="Projects" value={projects.length} />
          <Metric label="Papers" value={papers.length} />
          <Metric label="Notes" value={notes.length} />
        </div>
        <div className="metric-row triple">
          <Metric label="Experiments" value={experiments.length} />
          <Metric label={t.relatedWork} value={papers.filter((paper) => paper.status !== "inbox").length} />
          <Metric label={t.figures} value={t.figureItems.length} />
        </div>
      </div>
    </section>
  );
}

function Review({ t, moduleRows, summary, projects, papers, experiments }: {
  t: typeof ui.zh.review;
  moduleRows: Array<{ key: string; manages: string; content: string; status: string }>;
  summary: Summary | null;
  projects: Project[];
  papers: Paper[];
  experiments: Experiment[];
}) {
  return (
    <section className="dense-grid review-layout">
      <div className="panel wide accent-cyan">
        <h2>{t.moduleAudit}</h2>
        <div className="module-table">
          {moduleRows.map((row) => <div key={row.key}><strong>{row.key}</strong><span>{row.manages}</span><em>{row.content}</em><b>{row.status === "covered" ? "OK" : "TODO"}</b></div>)}
        </div>
      </div>
      <div className="panel accent-green">
        <h2>{t.weekly}</h2>
        <div className="metric-row"><Metric label={t.progress} value={summary?.active_projects ?? 0} /><Metric label={t.reading} value={summary?.papers ?? 0} /></div>
        <div className="metric-row"><Metric label={t.experiments} value={summary?.experiments ?? 0} /><Metric label={t.next} value={projects.filter((project) => project.progress < 100).length} /></div>
      </div>
      <div className="panel accent-rose">
        <h2>{t.monthly}</h2>
        <div className="review-list">
          <span>{t.reading}: {papers.length}</span>
          <span>{t.experiments}: {experiments.length}</span>
          <span>{t.progress}: {Math.round(projects.reduce((sum, item) => sum + item.progress, 0) / Math.max(projects.length, 1))}%</span>
        </div>
      </div>
      <div className="panel accent-amber">
        <h2>{t.semester}</h2>
        <textarea readOnly value={`${t.progress}\n\n${t.reading}\n\n${t.experiments}\n\n${t.next}`} />
      </div>
    </section>
  );
}

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

function splitLines(value?: string | null) {
  return (value || "").split(/\n+/).map((item) => item.trim()).filter(Boolean);
}

function findProjectName(projects: Project[], projectId: number) {
  return projects.find((project) => project.id === projectId)?.name ?? `Project #${projectId}`;
}

function PaperCard({ paper, langText }: { paper: Paper; langText: typeof ui.zh.paperCard }) {
  return <article className="paper-card"><span>{paper.venue} · {paper.year || langText.noYear}</span><h3>{paper.title}</h3><p>{paper.tags}</p>{paper.url && <a href={paper.url} target="_blank">{langText.open}</a>}</article>;
}

function WidgetTitle({ icon, title }: { icon: ReactNode; title: string }) {
  return <div className="widget-title">{icon}<strong>{title}</strong></div>;
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return <div className="metric"><span>{label}</span><strong>{value}</strong></div>;
}

function ProgressLine({ label, value }: { label: string; value: number }) {
  return <div className="progress-line"><div><span>{label}</span><strong>{Math.round(value)}%</strong></div><progress value={value} max={100} /></div>;
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

function normalizeVenue(value?: string | null) {
  if (!value) return "Others";
  const lower = value.toLowerCase();
  if (lower.includes("icra")) return "ICRA";
  if (lower.includes("iros")) return "IROS";
  if (lower.includes("robotics and automation letters") || lower.includes("ra-l")) return "RA-L";
  if (lower.includes("transactions on robotics") || lower.includes("t-ro")) return "T-RO";
  if (lower.includes("science robotics")) return "Science Robotics";
  return venues.includes(value) ? value : "Others";
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
