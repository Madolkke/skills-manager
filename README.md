# Skills Manager

这是 SkillHub 正式版工作区，用来管理标准 Skill bundle、不可变 `SkillVersion`、测评集版本、手工测评结果、运行环境上下文和历史证据链。

## 当前产品闭环

- `Skill` 是 SkillHub 中稳定可搜索的入口。
- `SkillVersion` 是不可变 Skill bundle 内容快照，可以来自标准 Skill 文件夹或 zip 导入后的 `skill_bundle` artifact。
- `EvalSetVersion` 是测试用例集合快照。
- `EvalRun` 记录一次 exact `SkillVersion + EvalSetVersion + run_context` 的通过/不通过结果、本次运行实际输出和 actual vs expected 证据。
- 运行环境标签只属于 `EvalRun`，例如 runner、model、OS 或 sandbox；同一个 `SkillVersion` 可以在不同环境下留下多次可追溯结果。
- Web V4 首页提供 Skill 搜索、筛选、维护者、当前版本、测评集版本、验证状态和可展开的最近测评入口。
- 新建 Skill 只需要上传标准 Skill bundle；名称和说明优先从 `SKILL.md` frontmatter 读取。
- `版本` 页展示 Skill 的不可变版本线、当前版本、bundle 文件摘要、后端 `GET /api/artifacts/diff` 返回的真实 diff 和版本详情。
- `测评集` 页只管理 case 和 case version；新增或编辑 case 会生成新的 `EvalSetVersion`。
- `测评` 页选择 exact `SkillVersion + EvalSetVersion`，输入运行环境标签和本次运行结果，逐条对照 expected output 后记录 `EvalRun`。
- `历史` 页展示 `SkillVersion`、`EvalSetVersion`、运行环境、case version、artifact digest、actual output 与 expected output 的证据链。

## 快速开始

正式版工作区位于 `apps/api` 和 `apps/web-v4`。主分支只保留当前正式版运行时代码、验证脚本和权威文档；旧前端工作台、早期 demo、prototype、Ralph/.agent 任务体系和历史截图已经移除。

### 一键本地运行

```bash
bash scripts/dev.sh
```

这个命令会启动：

- API: `http://127.0.0.1:8000`
- Web V4: `http://127.0.0.1:3030/skills`

脚本使用 `uv` 运行 Python API，并在 `apps/web-v4/node_modules` 缺失时安装前端依赖。脚本默认设置 `UV_NO_CACHE=1`，不会污染全局 Python 环境或依赖全局 uv cache 权限。

本地 API 数据默认持久化到 `.data/skillhub.sqlite3`。从干净 `git clone` 启动时不需要提前创建数据库文件，API 会自动创建 SQLite 文件和 schema；`bash scripts/dev.sh` 在 macOS、Linux 和 Windows Git Bash 下默认都会落到文件型 SQLite，不会回退到 `sqlite:///:memory:`。

可以用 `SKILLHUB_DATA_DIR` 覆盖数据目录；只有需要完整自定义连接串时才设置 `SKILLHUB_DATABASE_URL`。本地开发默认 actor 是 `product-operator`。

启动后检查：

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:3030/skills
```

### 手动运行

终端 1：

```bash
cd apps/api
mkdir -p ../../.data
SKILLHUB_DATA_DIR=../../.data \
UV_NO_CACHE=1 \
uv run uvicorn skillhub.api.main:app --host 127.0.0.1 --port 8000
```

终端 2：

```bash
cd apps/web-v4
npm install
VITE_SKILLHUB_API_URL=http://127.0.0.1:8000 \
npm run dev -- --host 127.0.0.1 --port 3030
```

## 建议试用路径

1. 打开 `http://127.0.0.1:3030/skills`。
2. 点 `新建 Skill`，上传根目录包含 `SKILL.md` 的文件夹或 zip。
3. 在 `概览` 查看根目录、维护者、状态、当前版本、测评集和可展开的 bundle 文件树。
4. 在 `版本` 页查看版本线和 bundle 摘要；点击 `Bundle diff` 使用后端 diff read model 查看增删改和 hunk；点击 `上传版本` 追加新的不可变 `SkillVersion`。
5. 在 `测评集` 页点击 `添加 case` 新增用例；点击 `编辑为新版本` 创建新的 case version 并更新当前 `EvalSetVersion`。
6. 在 `测评` 页选择 exact `SkillVersion + EvalSetVersion`，输入运行环境标签、OS、Runner、Model，逐条输入本次运行结果，和 expected output 对照后标记通过或不通过。
7. 在 `历史` 页查看 run、运行环境、case result、actual output 和 expected output 的证据链；刷新或重启后仍应能看到同一批数据。

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
| 3 | 版本 | 查看右侧版本线；点击 `Bundle diff` / `查看该版本详情`；上传新版 bundle | 追加新的 `SkillVersion`；当前版本在线性历史中清晰标出；inspector 使用后端 diff 数据展示变更文件、hunk 与 digest |
| 4 | 测评集 | 新增 case；再编辑已有 case 为新版本 | case version 增加；当前 `EvalSetVersion` 更新；case 列表能按序号、版本和状态扫读 |
| 5 | 测评 | 选择 exact `SkillVersion + EvalSetVersion`，输入运行环境与 actual output，逐 case 标记结果 | 详情区显示真实绑定信息；每个 case 都能对比 actual vs expected；未全部确认前不能记录 |
| 6 | 历史 | 打开 `历史` tab，选择刚记录的 run | 展示 run、运行环境、`SkillVersion`、`EvalSetVersion`、case result、artifact digest、actual output 与版本链 |

最小冒烟至少覆盖：新建 Skill、上传版本、查看 bundle、后端 Bundle diff、创建 case、手动测评 actual output 记录、历史证据链，以及 320px 小窗口无横向溢出。

## 验证命令

推送前运行：

```bash
cd apps/api
uv run pytest
```

```bash
cd apps/web-v4
npm run test
npm run lint
npm run build
npm run e2e
npm run e2e:visual
```

`npm run e2e` 会用临时 SQLite 数据库启动 API 和 Web V4，执行一次从新建 Skill 到历史证据链的正式流程冒烟，并额外用 `320x820` viewport 覆盖小窗口溢出回归。详见 [Web V4 E2E smoke](apps/web-v4/e2e/formal-flow.md)。

`npm run e2e:visual` 会用固定 seed 和 `1586x992` viewport 截取 5 个正式页面，防止 UI 布局、actual output 对比和 diff 入口偏离当前基线。详见 [Web V4 视觉 Smoke](apps/web-v4/e2e/visual-smoke.md)。

## 主要文档

- [API contract](docs/api-contract.md)
- [Formal architecture v0.1](docs/formal-architecture-v0.1.md)
- [Formal tech stack](docs/formal-tech-stack.md)
- [Formal UI design v0.1](docs/formal-ui-design.md)
- [代码库质量审计](docs/codebase-quality-audit-2026-05-27.md)
- [Web V4 E2E smoke](apps/web-v4/e2e/formal-flow.md)
- [Web V4 视觉 Smoke](apps/web-v4/e2e/visual-smoke.md)
