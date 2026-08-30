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
- 通过 Zotero 本地 API 导入论文条目
- 保留 Firefox 扩展作为 CARSI / PDF 捕获入口
- 按 `ICRA / IROS / RA-L / T-RO / Science Robotics / Others` 管理论文
- 将论文档案、阅读笔记和长期知识库分开
- 支持 Reading Note 模板
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
│   │       ├── services    # 业务服务：settings / papers / projects / dashboard
│   │       └── paper_integrations  # Zotero / OpenAlex / Crossref / 翻译
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
├── data                    # SQLite 数据库和 PDF linked files
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

## 数据存储

默认 SQLite 数据库：

```text
/home/robot/RoboResearch_Workbench/data/workbench.db
```

通过 Zotero / CARSI 捕获的 PDF 会作为 linked file 保存到：

```text
/home/robot/RoboResearch_Workbench/data/papers
```

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
后端测试：28 passed
前端构建：成功
```

## 设计原则

- 本地优先：数据和项目默认留在本机
- 工具连接：不重复造 Zotero、Obsidian、GitHub
- 三层分离：Paper 保存论文档案，Reading Note 保存阅读过程，Knowledge 保存长期知识链接
- 实验可回溯：Experiment 关联项目、配置、Git commit 和实验结果
- Git 谨慎操作：提交和推送必须可检查、可确认

## 后续方向

V1.5 / V2 可以继续加入：

- Tauri 桌面壳
- ROS2 / GPU 状态监控
- Obsidian vault 索引
- AI Research Copilot
- 本地 RAG
- Overleaf / LaTeX 写作辅助
