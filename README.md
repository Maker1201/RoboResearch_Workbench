# RoboResearch Workbench

面向具身智能、机器人学习与电子信息方向研究生的本地优先科研工作台。

它不是 Zotero、Obsidian、GitHub 或 Overleaf 的替代品，而是把这些工具连接起来，形成一条更顺手的科研工作流：

```text
论文检索 -> Zotero 归档 -> 阅读笔记 -> 知识沉淀 / 研究想法 -> 本地项目 -> 实验记录 -> 论文写作
```

## 功能概览

- 管理 `/home/robot` 下的真实本地科研项目
- 查看项目 Git 分支、remote、变更文件和最近提交
- 支持选择文件后提交 commit，push 需要单独确认
- 使用 OpenAlex + Crossref 检索论文
- 通过 Zotero 本地 API 导入论文条目，自动解析并挂载 PDF（开放获取兜底 + CARSI 扩展捕获）
- 按 `ICRA / IROS / RA-L / T-RO / Science Robotics / Others` 管理论文
- 阅读队列：优先级、阅读模式（SCAN/SKIM/READ/DEEP）、阅读专注计时
- AI 分诊：一键为队列生成一句话总结、相关度评分与建议阅读方式，队列按相关度排序
- AI 阅读草稿：解析 Zotero 本地 PDF 全文，按 12 节模板生成阅读笔记草稿
- 阅读笔记一键同步为 Zotero 子笔记（重复同步是更新，不是新建）
- 将论文档案、阅读笔记和长期知识库分开
- 支持实验记录：项目、配置、数据集、Git commit、指标、结果和结论
- 支持保存 Obsidian 路径或 `obsidian://` 链接

## 项目目录

```text
/home/robot/RoboResearch_Workbench
├── apps
│   ├── server              # FastAPI 后端
│   │   └── app
│   │       ├── main.py     # 应用入口：lifespan、CORS、注册路由
│   │       ├── bootstrap.py # 建表、轻量迁移、种子数据、集成接线
│   │       ├── routers     # 路由：system / settings / projects / git / tasks / papers / reading_notes / workspace
│   │       ├── services    # 业务服务：settings / papers / projects / dashboard / zotero_storage（PDF 定位与文本抽取）
│   │       └── paper_integrations  # Zotero / OpenAlex / Crossref / 翻译 / AI 阅读助手
│   └── web                 # React / Vite 前端
│       └── src
│           ├── App.tsx     # 根组件：状态、侧栏、模块切换
│           ├── views       # 各模块页面（总览/项目/文献/设置等 10 个）
│           ├── components  # 共享小组件
│           ├── api.ts      # 后端 API 客户端
│           ├── i18n.ts     # 中英双语字典
│           ├── constants.ts / utils.ts / types.ts
│           └── styles.css
├── extensions
│   └── academic-paper-finder
│       └── ...             # Firefox PDF/CARSI 捕获扩展
├── data                    # SQLite 数据库（PDF 不在这里，见下方“数据存储”）
├── docs
│   └── PROJECT_SPEC.md     # 项目说明书
├── start.sh                # 一键启动（后端 8770 + 前端 5176）
└── README.md
```

## 快速启动

一键启动（推荐）：

```bash
cd /home/robot/RoboResearch_Workbench
./start.sh
```

脚本会启动后端 `http://127.0.0.1:8770` 和前端 `http://127.0.0.1:5176`（端口被占用时自动顺延），并注入前端的后端地址。

### 1. 手动启动后端

```bash
cd /home/robot/RoboResearch_Workbench/apps/server
. .venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8770 --reload
```

后端地址：

```text
http://127.0.0.1:8770
```

健康检查：

```bash
curl http://127.0.0.1:8770/health
```

### 2. 手动启动前端

```bash
cd /home/robot/RoboResearch_Workbench/apps/web
VITE_API_BASE=http://127.0.0.1:8770 npm run dev -- --host 127.0.0.1
```

前端地址：

```text
http://127.0.0.1:5176/
```

## 首次安装依赖

如果 `.venv` 或 `node_modules` 不存在，先执行下面命令。

后端：

```bash
cd /home/robot/RoboResearch_Workbench/apps/server
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

前端：

```bash
cd /home/robot/RoboResearch_Workbench/apps/web
npm install
```

环境变量（可选，按需配置）：

```bash
cd /home/robot/RoboResearch_Workbench/apps/server
cp .env.example .env
```

`.env` 里可以配置论文标题/摘要翻译（`TRANSLATION_*`）和 AI 阅读助手（`AI_*`，见下方“阅读整理工作流”）。不配置时对应功能自动关闭，不影响其他模块。

## 数据存储

默认 SQLite 数据库：

```text
/home/robot/RoboResearch_Workbench/data/workbench.db
```

PDF 附件直接存放在 **Zotero 自己的数据目录**里（默认 `~/Zotero/storage/<附件key>/`），工作台数据库通过 `zotero_attachment_key` 定位它们，不重复保存副本。AI 读取 PDF 全文也走这条路径，目录可用环境变量 `ZOTERO_DATA_DIR` 覆盖。

## Firefox 扩展

扩展源码位置：

```text
/home/robot/RoboResearch_Workbench/extensions/academic-paper-finder
```

它负责：

- 打开 DOI、IEEE、Science Robotics、arXiv 等页面
- 利用 Firefox 当前登录状态处理 CARSI / 机构访问
- 捕获 PDF
- 回传到工作台后端并挂载到 Zotero 条目

扩展会优先连接：

```text
http://127.0.0.1:8770
```

如果需要在 Firefox 中临时加载扩展，可以打开：

```text
about:debugging#/runtime/this-firefox
```

然后选择 `manifest.json`。

## Git 安全规则

工作台不会自动执行：

```bash
git add .
```

提交代码时必须显式选择文件。以下内容默认会被拒绝提交或提醒谨慎处理：

- `.env`
- `checkpoints/`
- `datasets/`
- `outputs/`
- `runs/`
- `wandb/`
- `*.pt`
- `*.pth`
- `*.ckpt`
- `*.onnx`

Push 是独立操作，需要用户确认。

## 测试与构建

后端测试：

```bash
cd /home/robot/RoboResearch_Workbench/apps/server
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest
```

前端构建：

```bash
cd /home/robot/RoboResearch_Workbench/apps/web
npm run build
```

当前验证结果：

```text
后端测试：55 passed
前端构建：成功
```

## 设计原则

- 本地优先：数据和项目默认留在本机
- 工具连接：不重复造 Zotero、Obsidian、GitHub
- 三层分离：Paper 保存论文档案，Reading Note 保存阅读过程，Knowledge 保存长期知识链接
- 实验可回溯：Experiment 关联项目、配置、Git commit 和实验结果
- Git 谨慎操作：提交和推送必须可检查、可确认

## 阅读整理工作流

在 Zotero 里读 PDF，在工作台记笔记、做整理，AI 负责初稿和分诊：

1. **AI 分诊**：文献 → 阅读队列 → 点“AI 分诊”，为队列中的论文生成一句话总结、相关度评分和建议阅读方式（SCAN/SKIM/READ/DEEP），队列自动按相关度排序，可一键采纳建议的阅读模式。
2. **精读**：选中论文 → 点“开始阅读”（自动跳转 Zotero 打开 PDF 并开始计时）→ 点“AI 草稿”，AI 解析 PDF 全文按 12 节模板生成草稿笔记 → 边读边修正，重点补第 8 节（对我有用）、第 10 节（问题）、第 11 节（想法）。
3. **同步归档**：点“同步 Zotero”，笔记作为子笔记挂在 Zotero 条目下，重复点击是更新不是新建。
4. **知识沉淀**：笔记第 12 节的要点后续提炼到知识库（Knowledge 层）。

### AI 与 PDF 配置

**推荐直接在设置页配置**：工作台 → 设置 → 集成 → 「AI 阅读助手」卡片，勾选启用后填入 API 地址、API Key、模型名，点“测试连接”验证，保存即可（存入数据库，重启生效）。同一张卡片里还能设置研究方向、输出语言、PDF 字符上限和 Zotero 数据目录。

也可以用 `apps/server/.env` 配置（`AI_PROVIDER / AI_API_BASE / AI_API_KEY / AI_MODEL` 等，见 `.env.example`）——设置页留空的字段才会回退到环境变量。

- `ZOTERO_DATA_DIR`：Zotero 数据目录（含 `storage/`），AI 从这里读 PDF 全文；PDF 不可用时自动退化为仅标题+摘要模式。默认 `~/Zotero`，一般无需改动。
- `AI_RESEARCH_INTERESTS` 写上你的研究方向（如 `VLA, 机械臂操作`）可显著提升分诊和草稿质量。

相关端点：`POST /papers/ai/triage`、`POST /papers/{id}/ai/draft-note`、`POST /reading-notes/{id}/push-zotero`、`GET /papers/{id}/pdf-text`、`POST /api/settings/test/ai`。

## 后续方向

V1.5 / V2 可以继续加入：

- 知识库深化：把笔记第 12 节批量提炼成 Knowledge 条目，生成跨论文综述对比表
- 本地 RAG：对全部 PDF 建立向量索引，支持全文语义搜索和问答
- 工作台内嵌 PDF 阅读器（pdf.js），不想切到 Zotero 时直接在工作台读
- AI Research Copilot：跨笔记问答、研究想法推敲
- Tauri 桌面壳
- ROS2 / GPU 状态监控
- Obsidian vault 索引
- Overleaf / LaTeX 写作辅助
