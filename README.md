# Skills Manager

这是 SkillHub 正式版工作区，用来管理标准 Skill bundle、不可变 `SkillVersion`、测评集版本、Opencode 测评结果、运行环境上下文和历史证据链。

## 当前产品闭环

- `Skill` 是 SkillHub 中稳定可搜索的入口。
- `SkillVersion` 是不可变 Skill bundle 内容快照，可以来自标准 Skill 文件夹或 zip 导入后的 `skill_bundle` artifact。
- `EvalSetVersion` 是测试用例集合快照；未被任何 `EvalRun` 使用的当前版本作为工作版本，新增或编辑 case 不会刷出无意义版本，一旦有运行记录就自动保留历史快照。
- `EvalRun` 记录一次 exact `SkillVersion + EvalSetVersion + run_context` 的通过/不通过结果、本次运行输出、步骤判定和 Laminar 调试引用。
- 运行环境标签只属于 `EvalRun`，例如 runner、model、OS 或 sandbox；同一个 `SkillVersion` 可以在不同环境下留下多次可追溯结果。
- Web 首页提供 Skill 搜索、筛选、维护者、当前版本、测评集版本、验证状态和可展开的最近测评入口。
- 新建 Skill 只需要上传标准 Skill bundle；名称和说明优先从 `SKILL.md` frontmatter 读取。
- `版本` 页展示 Skill 的不可变版本线、当前版本、bundle 文件摘要、后端 `GET /api/artifacts/diff` 返回的真实 diff 和版本详情。
- `测评集` 页只管理测试场景和测试例版本；每个测试例包含工作目录 zip、连续步骤和每步判断模板。
- `测评` 页选择 exact `SkillVersion + EvalSetVersion`，通过 Opencode Runner 执行测试例，并由 Python 判断模板判定步骤结果，完成后聚合记录 `EvalRun`。
- `历史` 页展示 `SkillVersion`、`EvalSetVersion`、运行环境、case version、artifact digest、运行结果、步骤判定和 Laminar 引用。

## 快速开始

正式版工作区位于 `apps/api` 和 `apps/web`。主分支只保留当前正式版运行时代码、验证脚本和权威文档；旧前端工作台、早期 demo、prototype 和历史任务体系已经移除。

### 启动前准备

本项目的 PostgreSQL 不由 Docker Compose 管理，需要使用本机或外部 PostgreSQL，并在 `.env` 中配置连接串。推荐先复制示例配置：

```bash
cp .env.example .env
```

至少需要配置：

```env
SKILLHUB_DATABASE_URL=postgresql+psycopg://postgres@127.0.0.1:5432/skillhub
```

如果要使用 Opencode Runner，还需要配置：

```env
DEEPSEEK_API_KEY=<your-api-key>
OPENCODE_BASE_URL=http://127.0.0.1:4096
EVAL_WORKDIR_HOST=.data/eval-runs
LMNR_BASE_URL=http://127.0.0.1
LMNR_HTTP_PORT=8000
LMNR_PROJECT_API_KEY=<your-laminar-project-api-key>
```

应用启动时会自动同步所需 schema。首次启动前请确保目标数据库已经存在。

### Windows 一键本地运行

Windows PowerShell 推荐使用一键脚本启动 API、Web 和 Worker：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/dev.ps1
```

如果 PostgreSQL 和 Opencode 已经由你自行启动，推荐使用更明确的本地服务脚本：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start-local-services.ps1
```

这个脚本只启动本项目剩余服务：API、Web 和 Worker；不会启动或管理 PostgreSQL、Opencode。重复执行时会跳过已经监听的 API/Web 端口和已运行的 Worker，并把输出写入 `.logs`。如果只想启动 API 和 Web：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start-local-services.ps1 -SkipWorker
```

脚本会读取 `.env`，并启动：

- API: `http://127.0.0.1:8000`
- Web: `http://127.0.0.1:3030/skills`
- Worker: 消费 Opencode 测评任务队列

如果只想单独启动 Worker：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/worker.ps1
```

### Bash 本地运行

```bash
bash scripts/dev.sh
```

这个命令会启动：

- API: `http://127.0.0.1:8000`
- Web: `http://127.0.0.1:3030/skills`

脚本会读取 `.env`，使用 `uv` 运行 Python API，并在 `apps/web/node_modules` 缺失时安装前端依赖。脚本默认设置 `UV_NO_CACHE=1`，不会污染全局 Python 环境或依赖全局 uv cache 权限。

注意：`scripts/dev.sh` 只启动 API 和 Web，不启动 Worker。需要 Opencode Runner 时，另开终端启动：

```bash
bash scripts/worker.sh
```

本地开发默认 actor 是 `product-operator`。连接串示例：

```bash
export SKILLHUB_DATABASE_URL=postgresql+psycopg://postgres@127.0.0.1:5432/skillhub
bash scripts/dev.sh
```

### 局域网访问

如果要让同一局域网里的其他电脑访问，启动时绑定到所有网卡：

```bash
SKILLHUB_HOST=0.0.0.0 bash scripts/dev.sh
```

其他电脑访问：

```text
http://<启动机器的局域网 IP>:3030/skills
```

前端默认会用浏览器当前访问的 hostname 推导 API 地址，例如打开 `http://192.168.1.20:3030/skills` 时会请求 `http://192.168.1.20:8000`，不会再请求访问者自己电脑的 `127.0.0.1`。后端默认允许 localhost 和常见私有网段来源的 CORS；如果使用自定义域名，可以设置 `SKILLHUB_CORS_ALLOW_ORIGINS` 或 `SKILLHUB_CORS_ALLOW_ORIGIN_REGEX`。

启动后检查：

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:3030/skills
```

### 手动运行

终端 1：

```bash
cd apps/api
SKILLHUB_DATABASE_URL=postgresql+psycopg://postgres@127.0.0.1:5432/skillhub \
UV_NO_CACHE=1 \
uv run uvicorn skillhub.bootstrap.app:create_app --factory --host 127.0.0.1 --port 8000
```

终端 2：

```bash
cd apps/web
npm install
npm run dev -- --host 127.0.0.1 --port 3030
```

手动局域网运行时，把两个服务都绑定到 `0.0.0.0`，并设置 `VITE_SKILLHUB_API_PORT`：

```bash
cd apps/web
VITE_SKILLHUB_API_PORT=8000 npm run dev -- --host 0.0.0.0 --port 3030
```

终端 3，仅在需要 Opencode Runner 时启动：

```bash
bash scripts/worker.sh
```

Windows PowerShell：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/worker.ps1
```

### Opencode Runner 容器

Docker Compose 只负责启动 Opencode 容器，不启动 PostgreSQL、API、Web 或 Worker。

启动 Opencode：

```bash
docker compose up -d opencode
```

检查 Opencode：

```bash
curl http://127.0.0.1:4096/global/health
```

推荐的完整启动顺序：

1. 准备 PostgreSQL，并配置 `.env`。
2. 启动 Opencode：`docker compose up -d opencode`。
3. 启动 API/Web/Worker：Windows 用 `scripts/dev.ps1`；Bash 用 `scripts/dev.sh` 加 `scripts/worker.sh`。

Opencode 监听本机 `http://127.0.0.1:4096`，不配置密码鉴权。`EVAL_WORKDIR_HOST` 默认是 `.data/eval-runs`，会挂载到 Opencode 容器内的 `/workspace/eval-runs`，Worker 也会在这个目录下创建每次测评的工作目录。

Laminar 负责保存外部 trace/eval 结果。Worker 需要 `LMNR_PROJECT_API_KEY` 才能执行新版测评；如果是本机自托管 Laminar，通常配置 `LMNR_BASE_URL=http://127.0.0.1` 和 `LMNR_HTTP_PORT=8000`。Opencode trace 需要在启动 Opencode 的环境中也带上同一个 `LMNR_PROJECT_API_KEY`。

常用端口：

| 服务 | 地址 | 说明 |
| --- | --- | --- |
| Web | `http://127.0.0.1:3030/skills` | 前端页面 |
| API | `http://127.0.0.1:8000` | 后端服务 |
| Opencode | `http://127.0.0.1:4096` | Opencode Server API |
| Laminar | `.env` 中的 `LMNR_BASE_URL` / `LMNR_HTTP_PORT` | trace 与 eval 结果平台 |
| PostgreSQL | `.env` 中的 `SKILLHUB_DATABASE_URL` | 本机或外部数据库 |

## 建议试用路径

1. 打开 `http://127.0.0.1:3030/skills`。
2. 点 `新建 Skill`，上传根目录包含 `SKILL.md` 的文件夹或 zip。
3. 在 `概览` 查看根目录、维护者、状态、当前版本、测评集和可展开的 bundle 文件树。
4. 在 `版本` 页查看版本线、bundle 摘要和后端 diff read model 返回的增删改 hunk；点击 `上传版本` 追加新的不可变 `SkillVersion`。
5. 在 `测评集` 页点击 `添加测试场景` 新增用例，上传可选工作目录 zip，并为每一步选择判断模板。
6. 在 `测评` 页选择 exact `SkillVersion + EvalSetVersion`，运行单个测试例或运行全部，等待 Opencode Runner 写回结果后聚合测评记录。
7. 在 `历史` 页查看 run、运行环境、case result、运行结果、步骤判定和 Laminar 引用；刷新或重启后仍应能看到同一批数据。

`SKILL.md` 必须以 frontmatter 开头：

```markdown
---
name: security-reviewing
description: Review pull requests for auth and data access regressions.
---

# Security Reviewing
```

导入后的 bundle 会作为不可变 `skill_bundle` artifact 保存，创建出的 `SkillVersion` 指向这个 artifact。如果缺少 `SKILL.md`、frontmatter 不合法、缺少 `name`/`description`，或 zip 无法读取，页面会在导入表单顶部显示错误摘要。

## 核心验收清单

| 步骤 | 页面 | 操作 | 期望结果 |
| --- | --- | --- | --- |
| 1 | Hub 首页 | 点击 `新建 Skill`，上传标准 Skill 文件夹或 zip | 创建后进入 Skill 详情页；首页可搜索到该 Skill；卡片能看到维护者、当前版本和测评集版本 |
| 2 | Skill 概览 | 查看 summary 身份卡；展开 bundle 文件夹并切换文件 | 显示真实根目录、维护者和状态；右侧显示对应文件内容、路径和 digest |
| 3 | 版本 | 查看版本节点、bundle 内容和 diff；上传新版 bundle | 追加新的 `SkillVersion`；当前版本在线性历史中清晰标出；页面直接使用后端 diff 数据展示变更文件、hunk 与 digest |
| 4 | 测评集 | 新增测试场景；再编辑已有测试场景 | case version 增加；每个步骤都有输入和判断模板；工作目录 zip 可被保存 |
| 5 | 测评 | 选择 exact `SkillVersion + EvalSetVersion`，运行单个测试例或运行全部 | 详情区显示真实绑定信息；每个测试例都能追踪任务状态、步骤判定、运行结果和 Laminar 引用；未全部完成前不能聚合 |
| 6 | 历史 | 打开 `历史` tab，选择刚记录的 run | 展示 run、运行环境、`SkillVersion`、`EvalSetVersion`、case result、artifact digest、运行结果与版本链 |

最小冒烟覆盖：新建 Skill、上传版本、查看 bundle、后端 Bundle diff、创建多步骤测试场景、Opencode Runner 完成步骤判定、Laminar 记录 eval 结果、历史证据链，以及 320px 小窗口无横向溢出。

## 验证命令

推送前运行：

```bash
cd apps/api
SKILLHUB_TEST_DATABASE_URL=postgresql+psycopg://postgres@127.0.0.1:5432/skillhub_test \
uv run pytest
```

```bash
cd apps/web
npm run test
npm run lint
npm run build
```

## 主要文档

- [API contract](docs/api-contract.md)
- [架构说明](docs/architecture.md)
- [技术栈](docs/tech-stack.md)
- [UI 设计规格](docs/ui-design.md)
- [验证与仓库约定](docs/verification.md)
