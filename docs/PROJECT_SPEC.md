# RoboResearch Workbench 项目需求与系统设计说明书 v1.0

## 1. 项目定位

RoboResearch Workbench 是一个面向电子信息与具身智能机器人方向研究生的本地优先科研工作台。它不替代 Zotero、Obsidian、GitHub 或 Overleaf，而是把它们连接成一条可执行的科研链路：

```text
Paper -> Reading Note -> Knowledge / Idea / Project -> Experiment -> Writing
```

第一版重点解决日常科研管理：项目、论文、读文献笔记、实验记录、Git 状态、知识链接和 Dashboard。

## 2. 技术栈

| Layer | Stack |
|---|---|
| Frontend | React + TypeScript + Vite |
| UI | CSS variables + responsive workbench layout |
| Dashboard Layout | react-grid-layout |
| State/Data | TanStack Query + small local component state |
| Backend | Python 3.12 + FastAPI |
| Database | SQLite |
| ORM | SQLAlchemy 2 |
| Validation | Pydantic |
| Git | system Git subprocess |
| Paper Search | OpenAlex + Crossref |
| Zotero | Zotero local API |
| Obsidian | URI/path links |

## 3. Core Modules

### Dashboard

Dashboard 是每天打开的首页。它显示今日任务、活跃项目、论文队列、实验状态、快速记录和知识链接。布局由用户拖拽调整，并保存到后端。

### Projects

Project 映射真实本地目录，例如 `/home/robot/IsaacLab` 或 `/home/robot/LLM-as-BT-Planner`。每个项目可以关联 milestones、tasks、papers、experiments 和 Git remote。

### Git Panel

Git Panel 提供 `status`、`diff`、recent commits、commit、push。安全策略：

- 不自动执行 `git add .`
- commit 必须传入明确文件列表
- push 必须由用户点击确认
- 默认提醒排除 `.env`、checkpoints、datasets、runs 等大文件或敏感文件

### Papers

Paper 是论文档案，不是阅读笔记。一级分类使用 Venue：

```text
ICRA / IROS / RA-L / T-RO / Science Robotics / Others
```

Tags 作为研究方向维度，如 VLA、VLM、Manipulation、SLAM、Diffusion Policy、ROS2。

### Reading Notes

Reading Note 保存读某篇论文时的理解、问题、批判、idea 和可提取知识。它允许草稿化和不完美，不要求成为长期知识库。

### Knowledge

Knowledge 不复制 Obsidian 全量内容。Workbench 只保存知识标题、主题、Obsidian URI 或 vault 相对路径，并支持从 Reading Note 关联过去。

### Experiments

Experiment 记录项目、日期、Git commit、config、dataset、metrics、result 和 conclusion。目标是让论文实验章节能从记录里回溯，而不是靠记忆。

## 4. Data Model

主要实体：

- `Project`
- `Milestone`
- `Task`
- `Paper`
- `ReadingNote`
- `Experiment`
- `ResearchIdea`
- `KnowledgeLink`
- `DashboardLayout`
- `Setting`

数据库默认路径：

```text
/home/robot/RoboResearch_Workbench/data/workbench.db
```

## 5. API Surface

Core:

- `GET /health`
- `GET /summary`
- `GET/PUT /dashboard/layout`

Projects:

- `GET /projects`
- `POST /projects`
- `PATCH /projects/{project_id}`
- `DELETE /projects/{project_id}`
- `GET /projects/discover`
- `GET /projects/{project_id}/git/status`
- `GET /projects/{project_id}/git/diff`
- `POST /projects/{project_id}/git/commit`
- `POST /projects/{project_id}/git/push`

Papers:

- `POST /papers/search`
- `POST /papers/import-zotero`
- `POST /papers/attach-pdf`
- `GET/POST/PATCH/DELETE /papers`

Notes and Research:

- `GET/POST/PATCH/DELETE /reading-notes`
- `GET/POST/PATCH/DELETE /experiments`
- `GET/POST/PATCH/DELETE /knowledge-links`

## 6. Existing Zotero Plugin Integration

The existing plugin at `/home/robot/Zotero/学术论文检索助手浏览器插件` is reused as follows:

- Backend search/import logic is migrated into `apps/server/app/paper_integrations`.
- Firefox extension source is copied into `extensions/academic-paper-finder`.
- Sensitive files such as `.env`, `.amo-credentials`, `.amo-upload-uuid`, signed packages, logs, and downloaded papers are not copied.
- The extension continues to capture CARSI/PDF sessions and calls the workbench backend.

## 7. V1 Acceptance Criteria

- Backend starts at `http://127.0.0.1:8765`.
- Frontend starts through Vite and can call the backend.
- Dashboard loads and saves layout.
- Projects can register local paths and read Git status.
- Papers can search OpenAlex/Crossref, save to the workbench, and import to Zotero.
- Reading Notes can be created from a paper.
- Experiments can be linked to a project and Git commit.
- Knowledge links can open Obsidian URIs or stored paths.
- `pytest` and `npm run build` pass.

## 8. Deferred

V1 does not include Tauri, cloud sync, multi-user collaboration, full Obsidian vault indexing, ROS2/GPU monitoring, AI Assistant, or RAG.

