import { useEffect, useState } from "react";
import {
  BarChart3,
  BookOpen,
  Boxes,
  CalendarDays,
  Check,
  FlaskConical,
  Languages,
  LayoutDashboard,
  Link,
  Loader2,
  PenLine,
  Settings as SettingsIcon,
  ShieldCheck,
} from "lucide-react";
import { api } from "./api";
import type { DashboardSummary, Experiment, KnowledgeLink, Paper, Project, ReadingNote, Summary, SystemSettings, Task } from "./types";
import { coreModuleRows, type Tab } from "./constants";
import { ui, type Lang } from "./i18n";
import { friendlyError } from "./utils";
import { Dashboard, FocusMode } from "./views/Dashboard";
import { Experiments } from "./views/Experiments";
import { Knowledge } from "./views/Knowledge";
import { Papers } from "./views/Papers";
import { Projects } from "./views/Projects";
import { ResearchWriting } from "./views/ResearchWriting";
import { Review } from "./views/Review";
import { SettingsPage } from "./views/Settings";
import { StudyLife } from "./views/StudyLife";

const TAB_KEYS: Tab[] = ["dashboard", "study", "projects", "papers", "knowledge", "research", "review", "experiments", "settings"];

function initialTab(): Tab {
  const saved = localStorage.getItem("rrw-tab");
  return TAB_KEYS.includes(saved as Tab) ? (saved as Tab) : "dashboard";
}

export default function App() {
  const [tab, setTab] = useState<Tab>(initialTab);
  const [lang, setLang] = useState<Lang>(() => (localStorage.getItem("rrw-lang") === "en" ? "en" : "zh"));
  const [summary, setSummary] = useState<Summary | null>(null);
  const [dashboardSummary, setDashboardSummary] = useState<DashboardSummary | null>(null);
  const [settings, setSettings] = useState<SystemSettings | null>(null);
  const [focusMode, setFocusMode] = useState(false);
  const [studyDate, setStudyDate] = useState<string | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [papers, setPapers] = useState<Paper[]>([]);
  const [notes, setNotes] = useState<ReadingNote[]>([]);
  const [experiments, setExperiments] = useState<Experiment[]>([]);
  const [knowledge, setKnowledge] = useState<KnowledgeLink[]>([]);
  const [message, setMessage] = useState<string>(ui[lang].connecting);
  const [loading, setLoading] = useState(false);
  const t = ui[lang];

  useEffect(() => {
    localStorage.setItem("rrw-tab", tab);
  }, [tab]);

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
        <button className="language-toggle" onClick={switchLanguage} title="语言">
          <Languages size={17} />
          {lang === "zh" ? "中文" : "英文"}
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

        {tab === "dashboard" && (focusMode ? <FocusMode t={t.focusMode} tasks={tasks} projects={projects} summary={dashboardSummary} refresh={refresh} exit={() => setFocusMode(false)} /> : <Dashboard t={t.dashboard} summary={dashboardSummary} tasks={tasks} refresh={refresh} openFocus={() => setFocusMode(true)} setTab={setTab} openStudyDate={(date) => {
          setStudyDate(date);
          setTab("study");
        }} />)}
        {tab === "study" && <StudyLife t={t.study} tasks={tasks} refresh={refresh} initialDate={studyDate} />}
        {tab === "projects" && <Projects t={t.projects} projects={projects} refresh={refresh} />}
        {tab === "papers" && <Papers t={t.papers} papers={papers} projects={projects} notes={notes} refresh={refresh} setMessage={setMessage} setLoading={setLoading} />}
        {tab === "knowledge" && <Knowledge t={t.knowledge} knowledge={knowledge} papers={papers} refresh={refresh} />}
        {tab === "research" && <ResearchWriting t={t.research} projects={projects} papers={papers} notes={notes} experiments={experiments} />}
        {tab === "review" && <Review t={t.review} moduleRows={coreModuleRows[lang]} summary={summary} projects={projects} papers={papers} experiments={experiments} />}
        {tab === "experiments" && <Experiments t={t.experiments} projects={projects} refresh={refresh} />}
        {tab === "settings" && settings && <SettingsPage t={t.settings} settings={settings} setSettings={setSettings} setLang={setLang} setMessage={setMessage} />}
      </main>
    </div>
  );
}
