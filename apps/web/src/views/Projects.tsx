import { useEffect, useMemo, useRef, useState } from "react";
import { ChevronLeft, Eye, FolderOpen, GitBranch, GitCommitHorizontal, History, Link, Plus, RefreshCw, RotateCcw, Save, Search, Send, SettingsIcon, ShieldCheck, SlidersHorizontal, Trash2, UploadCloud } from "lucide-react";
import { api } from "../api";
import type { DirectoryListing, Experiment, GitActionResult, GitCommit, GitSecurityScan, Project, ProjectDetail, ProjectProgress, ProjectScan, ProjectStage, GitVersionDetail } from "../types";
import { ui } from "../i18n";
import { Metric } from "../components/Metric";
import { ProgressLine } from "../components/ProgressLine";
import { ProjectCard } from "../components/ProjectCard";
import { SecurityScan } from "../components/SecurityScan";
import { detectionLabels, friendlyError, githubWebUrl, healthText, projectStatusText, projectTabLabels, registrationCaseText, stageStatusText } from "../utils";

export function Projects({ t: _t, projects, refresh }: { t: typeof ui.zh.projects; projects: Project[]; refresh: () => Promise<void> }) {
  const statuses = ["", "Planning", "Active", "Blocked", "Paused", "Completed", "Archived"];
  const [items, setItems] = useState<Project[]>(projects);
  const [selected, setSelected] = useState<Project | null>(projects[0] ?? null);
  const [detail, setDetail] = useState<ProjectDetail | null>(null);
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
  const [selectedVersion, setSelectedVersion] = useState<GitVersionDetail | null>(null);
  const [branchName, setBranchName] = useState("");
  const [publish, setPublish] = useState({ repository_name: "", description: "", visibility: "private", default_branch: "main", confirm_risks: false });
  const [securityScan, setSecurityScan] = useState<GitSecurityScan | null>(null);
  const [stageDrafts, setStageDrafts] = useState<Record<number, { status: string; progress: number; weight: number }>>({});
  const [newStage, setNewStage] = useState({ title: "", status: "pending", progress: 0, weight: 1 });
  const detailRequestSeq = useRef(0);

  useEffect(() => setItems(projects), [projects]);
  useEffect(() => {
    if (!selected && items[0]) setSelected(items[0]);
  }, [items, selected]);
  useEffect(() => {
    if (selected) void loadDetail(selected.id);
  }, [selected?.id]);
  useEffect(() => {
    // 列表接口不再逐项目跑 git 子进程，进入项目页时批量刷新一次 Git 状态
    void (async () => {
      try {
        await api.refreshProjectsGit();
        await refresh();
      } catch {
        // 后端离线时由顶栏连接状态提示
      }
    })();
  }, []);

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
    const requestSeq = ++detailRequestSeq.current;
    const data = await api.projectDetail(id);
    if (requestSeq !== detailRequestSeq.current) return;
    setDetail(data);
    setSelected(data.project);
    setItems((current) => current.map((project) => project.id === data.project.id ? data.project : project));
    setStageDrafts(Object.fromEntries((data.progress?.stages || []).filter((stage: ProjectStage) => stage.id).map((stage: ProjectStage) => [stage.id, { status: stage.status, progress: stage.progress, weight: stage.weight }])));
    setChecked([]);
    setDiff("");
    setPublish((current) => ({ ...current, repository_name: data.project.name, description: data.project.description || "", default_branch: data.project.default_branch || data.git?.branch || "main" }));
    if (activeTab === "versions") await loadVersions(id);
  }

  function selectProject(project: Project) {
    setSelected(project);
    setDetail(null);
    setChecked([]);
    setDiff("");
    setVersions([]);
    setSelectedVersion(null);
    setSecurityScan(null);
    setMessage("");
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

  async function gitAction(action: () => Promise<GitActionResult>, success: string) {
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
    const selectable = git.changes.map((change) => change.path).filter((path: string) => safe.has(path));
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

  async function deleteSelectedProject() {
    if (!selectedProject) return;
    const confirmed = window.confirm(`从工作台移除项目“${selectedProject.name}”？本地文件夹不会被删除。`);
    if (!confirmed) return;
    try {
      await api.deleteProject(selectedProject.id);
      const remaining = items.filter((project) => project.id !== selectedProject.id);
      detailRequestSeq.current += 1;
      setItems(remaining);
      setDetail(null);
      setChecked([]);
      setDiff("");
      setVersions([]);
      setSelectedVersion(null);
      setSecurityScan(null);
      setSelected(remaining[0] ?? null);
      setMessage(`已从工作台移除 ${selectedProject.name}。本地文件夹未删除。`);
      await refresh();
    } catch (error) {
      setMessage(`删除失败：${friendlyError(error)}`);
    }
  }

  async function saveProjectSettings() {
    if (!selected || !detail?.project) return;
    const updated = await api.updateProject(selected.id, detail.project);
    setSelected(updated);
    setDetail((current) => current ? { ...current, project: updated } : current);
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

  function updateProjectField(patch: Partial<Project>) {
    setDetail((current) => (current ? { ...current, project: { ...current.project, ...patch } } : current));
  }

  async function initializeDefaultStages() {
    if (!selected) return;
    const data = await api.initializeProjectProgress(selected.id);
    setDetail((current) => ({ ...(current || {}), ...data }));
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
  const selectedProject = (detail?.project ?? selected) as Project | undefined;

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
          {items.map((project) => <ProjectCard key={project.id} project={project} selected={selected?.id === project.id} onClick={() => selectProject(project)} />)}
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
                  <div className="toolbar"><button onClick={() => void gitAction(() => api.gitInit(selectedProject.id), "Git 已初始化。")}><GitBranch size={16} />初始化 Git</button><button onClick={() => void gitAction(() => api.gitPull(selectedProject.id, git?.branch || undefined), "拉取完成。") }><RefreshCw size={16} />拉取</button><button onClick={() => void gitAction(() => api.gitPush(selectedProject.id, git?.branch || undefined), "推送完成。") }><Send size={16} />推送</button><button onClick={() => void api.prePushCheck(selectedProject.id).then(setSecurityScan)}><ShieldCheck size={16} />安全检查</button></div>
                  <div className="toolbar"><button disabled={!git?.changes?.length} onClick={() => void selectAllSafeChanges()}>全选安全文件</button><button disabled={!checked.length} onClick={() => setChecked([])}>清空选择</button><span className="muted">已选择 {checked.length} / {git?.changes?.length || 0}</span></div>
                  <div className="changes">{git?.changes?.map((change) => <label key={change.path}><input type="checkbox" checked={checked.includes(change.path)} onChange={(event) => setChecked((items) => event.target.checked ? Array.from(new Set([...items, change.path])) : items.filter((item) => item !== change.path))} /><code>{change.status}</code><button className="link-button" onClick={() => void showDiff(change.path)}>{change.path}</button></label>)}</div>
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

            {activeTab === "settings" && detail && (
              <div className="panel-lite">
                <h3>项目设置</h3>
                <div className="form-grid settings-grid">
                  <label><span>项目名称</span><input value={detail.project.name || ""} onChange={(event) => updateProjectField({ name: event.target.value })} /></label>
                  <label><span>项目状态</span><select value={detail.project.status || "Active"} onChange={(event) => updateProjectField({ status: event.target.value })}>{statuses.filter(Boolean).map((item) => <option key={item} value={item}>{projectStatusText(item)}</option>)}</select></label>
                  <label><span>当前阶段</span><input value={detail.project.current_stage || ""} onChange={(event) => updateProjectField({ current_stage: event.target.value })} placeholder="例如：Baseline 复现" /></label>
                  <label><span>下一阶段</span><input value={detail.project.next_stage || ""} onChange={(event) => updateProjectField({ next_stage: event.target.value })} placeholder="例如：真实机器人测试" /></label>
                  <label><span>进度模式</span><select value={detail.project.progress_mode || "AUTO"} onChange={(event) => updateProjectField({ progress_mode: event.target.value })}><option value="AUTO">自动计算进度</option><option value="MANUAL">手动设置进度</option></select></label>
                  <label><span>手动总进度</span><input type="number" min="0" max="100" value={detail.project.progress || 0} onChange={(event) => updateProjectField({ progress: Number(event.target.value) })} disabled={detail.project.progress_mode !== "MANUAL"} /></label>
                  <label><span>默认分支</span><input value={detail.project.default_branch || ""} onChange={(event) => updateProjectField({ default_branch: event.target.value })} placeholder="默认分支" /></label>
                  <label><span>实验目录</span><input value={detail.project.experiment_dir || ""} onChange={(event) => updateProjectField({ experiment_dir: event.target.value })} placeholder="实验目录" /></label>
                  <label><span>结果目录</span><input value={detail.project.results_dir || ""} onChange={(event) => updateProjectField({ results_dir: event.target.value })} placeholder="结果目录" /></label>
                  <label className="full-field"><span>项目描述</span><textarea value={detail.project.description || ""} onChange={(event) => updateProjectField({ description: event.target.value })} /></label>
                  <button className="primary" onClick={() => void saveProjectSettings()}><SettingsIcon size={16} />保存项目设置</button>
                  <button className="danger" onClick={() => void deleteSelectedProject()}><Trash2 size={16} />从工作台移除</button>
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

