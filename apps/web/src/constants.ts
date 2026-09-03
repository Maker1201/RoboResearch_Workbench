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

export type Tab = "dashboard" | "study" | "projects" | "papers" | "knowledge" | "research" | "experiments" | "settings";
