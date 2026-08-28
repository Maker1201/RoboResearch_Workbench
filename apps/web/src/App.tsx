import { useEffect, useState, type ReactNode } from "react";
import {
  BarChart3,
  BookOpen,
  Boxes,
  CalendarDays,
  Check,
  ChevronLeft,
  ChevronRight,
  Circle,
  CircleCheck,
  Clock3,
  FlaskConical,
  GitBranch,
  Languages,
  LayoutDashboard,
  Link,
  Loader2,
  Pause,
  Play,
  NotebookPen,
  PenLine,
  Plus,
  Search,
  Send,
  Settings as SettingsIcon,
  ShieldCheck,
  Timer,
  Trash2,
  X,
} from "lucide-react";
import { api } from "./api";
import type { DashboardSummary, Experiment, FocusSession, KnowledgeLink, Paper, Project, ReadingNote, SearchPaper, Summary, SystemSettings, Task } from "./types";

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
    refresh: "Refresh",
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
      registerTitle: "Register Local Project",
      projectName: "Project name",
      projectPath: "/home/robot/project",
      register: "Register",
      gitPanel: "Git Panel",
      gitStatus: "Git Status",
      push: "Push",
      branch: "Branch",
      remote: "Remote",
      unknown: "unknown",
      none: "none",
      commitMessage: "Commit message",
      commitSelected: "Commit Selected",
      commitOk: "Commit created.",
      commitFailed: "Commit failed.",
      pushOk: "Push completed.",
      pushFailed: "Push failed.",
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
      unknown: "Unknown",
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

function Projects({ t, projects, refresh }: { t: typeof ui.zh.projects; projects: Project[]; refresh: () => Promise<void> }) {
  const [path, setPath] = useState("/home/robot/IsaacLab");
  const [name, setName] = useState("IsaacLab");
  const [selected, setSelected] = useState<Project | null>(projects[0] ?? null);
  const [git, setGit] = useState<any>(null);
  const [message, setMessage] = useState("");
  const [commitMessage, setCommitMessage] = useState("");
  const [checked, setChecked] = useState<string[]>([]);

  useEffect(() => {
    if (!selected && projects[0]) setSelected(projects[0]);
  }, [projects, selected]);

  async function register() {
    await api.createProject({ name, path, status: "active", progress: 0 });
    await refresh();
  }

  async function loadGit(project = selected) {
    if (!project) return;
    const data = await api.gitStatus(project.id);
    setGit(data);
    setChecked([]);
  }

  async function commit() {
    if (!selected) return;
    const result = await api.gitCommit(selected.id, checked, commitMessage);
    setMessage(result.ok ? t.commitOk : result.stderr || t.commitFailed);
    await loadGit(selected);
  }

  async function push() {
    if (!selected) return;
    const result = await api.gitPush(selected.id, git?.branch);
    setMessage(result.ok ? t.pushOk : result.stderr || t.pushFailed);
  }

  return (
    <section className="page-grid">
      <div className="panel">
        <h2>{t.registerTitle}</h2>
        <div className="form-grid">
          <input value={name} onChange={(event) => setName(event.target.value)} placeholder={t.projectName} />
          <input value={path} onChange={(event) => setPath(event.target.value)} placeholder={t.projectPath} />
          <button className="primary" onClick={() => void register()}><Plus size={16} />{t.register}</button>
        </div>
        <div className="list">
          {projects.map((project) => (
            <button key={project.id} className={`list-item ${selected?.id === project.id ? "selected" : ""}`} onClick={() => { setSelected(project); void loadGit(project); }}>
              <strong>{project.name}</strong>
              <span>{project.path}</span>
            </button>
          ))}
        </div>
      </div>
      <div className="panel wide">
        <h2>{t.gitPanel}</h2>
        <div className="toolbar">
          <button onClick={() => void loadGit()}><GitBranch size={16} />{t.gitStatus}</button>
          <button onClick={() => void push()}><Send size={16} />{t.push}</button>
        </div>
        {git && (
          <>
            <div className="metric-row">
              <Metric label={t.branch} value={git.branch || t.unknown} />
              <Metric label={t.remote} value={git.remote_url ? "origin" : t.none} />
            </div>
            <div className="changes">
              {git.changes.map((change: any) => (
                <label key={change.path}>
                  <input type="checkbox" checked={checked.includes(change.path)} onChange={(event) => {
                    setChecked((items) => event.target.checked ? [...items, change.path] : items.filter((item) => item !== change.path));
                  }} />
                  <code>{change.status}</code>
                  <span>{change.path}</span>
                </label>
              ))}
            </div>
            <div className="form-grid">
              <input value={commitMessage} onChange={(event) => setCommitMessage(event.target.value)} placeholder={t.commitMessage} />
              <button className="primary" onClick={() => void commit()}>{t.commitSelected}</button>
            </div>
            <pre>{git.recent_commits?.join("\n")}</pre>
          </>
        )}
        {message && <p className="notice">{message}</p>}
      </div>
    </section>
  );
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
  return error instanceof Error ? error.message : String(error);
}
