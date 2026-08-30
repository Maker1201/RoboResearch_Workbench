export const venues = ["ICRA", "IROS", "RA-L", "T-RO", "Science Robotics", "Others"];
export const defaultSources = [
  { id: "icra", label: "ICRA", kind: "conference", aliases: ["IEEE International Conference on Robotics and Automation"], openalex_ids: [] },
  { id: "iros", label: "IROS", kind: "conference", aliases: ["IEEE/RSJ International Conference on Intelligent Robots and Systems"], openalex_ids: [] },
  { id: "ral", label: "RA-L", kind: "journal", aliases: ["IEEE Robotics and Automation Letters"], openalex_ids: [] },
  { id: "science-robotics", label: "Science Robotics", kind: "journal", aliases: ["Science Robotics"], openalex_ids: [] },
  { id: "tro", label: "T-RO", kind: "journal", aliases: ["IEEE Transactions on Robotics"], openalex_ids: [] },
];
export const readingStatuses = ["Inbox", "Candidate", "To Read", "Skimming", "Reading", "Deep Reading", "Finished", "Reference", "Dropped"];
export const readingModes = ["SCAN", "SKIM", "READ", "DEEP"];
export const readingPurposes = ["Project", "Literature Review", "Learn Method", "Reproduce", "Compare Baseline", "Research Idea", "General Interest"];
export const paperPriorities = ["high", "normal", "low"];
export const literatureSections = ["Search", "Candidates", "Library", "Reading Queue", "Reading Notes", "Collections"];
export const literatureSectionLabels: Record<string, string> = {
  Search: "文献检索",
  Candidates: "候选文献",
  Library: "文献库",
  "Reading Queue": "阅读队列",
  "Reading Notes": "阅读笔记",
  Collections: "合集",
};
export const topicFilters = ["VLA", "导航", "操作", "SLAM", "机器人学习"];

export type Tab = "dashboard" | "study" | "projects" | "papers" | "knowledge" | "research" | "review" | "notes" | "experiments" | "settings";


export const coreModuleRows = {
  zh: [
    { key: "总览", manages: "每天真正要看的首页", content: "今日任务 / 本周目标 / 项目进度 / 待读论文", status: "covered" },
    { key: "学习 & 生活", manages: "日程和个人节奏", content: "课程 / 学习计划 / 英语 / 运动 / 会议", status: "covered" },
    { key: "项目", manages: "机器人科研项目", content: "VLA / 导航 / 操作 / ROS2 / 实验记录", status: "covered" },
    { key: "文献", manages: "文献管理", content: "阅读队列 / 精读笔记 / 相关工作 / 引用", status: "covered" },
    { key: "知识库", manages: "长期知识库", content: "SLAM / RL / Transformer / 控制 / ROS2", status: "covered" },
    { key: "研究与写作", manages: "论文研究全过程", content: "想法 / 实验 / 图表 / 草稿 / 投稿", status: "covered" },
    { key: "复盘", manages: "周/月/学期复盘", content: "项目进展 / 阅读量 / 实验结果 / 下阶段计划", status: "covered" },
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
