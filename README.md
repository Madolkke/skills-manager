# Skills Manager

这是一个带测评证据的 SkillHub 产品工作区，用来管理标准 Skill bundle、约束变体、不可变版本、评测集版本、手工测评结果，以及“是否设为当前版本”的证据化决策。

## 当前产品闭环

- `Skill` 是 SkillHub 中稳定可搜索的入口。
- `Variant` 是某组 tag 约束下人工维护的当前最优解。
- `VariantVersion` 是不可变内容快照，可以是标准 Skill 文件夹或 zip 导入后的 `skill_bundle` artifact。
- `EvalSetVersion` 是测试用例版本快照。
- `EvalRun` 记录一次 exact `VariantVersion + EvalSetVersion` 的通过/不通过结果。
- Web V4 首页提供 Skill 搜索、筛选、维护者、当前版本、测评集版本、验证状态和可展开的最近测评入口，并以 `docs/product-ui-reference/` 下 5 张正式版参考图为视觉目标；最近测评的 `查看全部` 是首页右栏内的列表展开，不伪造跨 Skill 全局历史页。
- 新建 Skill 只需要上传标准 Skill bundle 并输入 tag；名称和说明优先从 `SKILL.md` frontmatter 读取。
- Skill 概览展示根目录、维护者、状态、说明、默认变体、当前版本、验证分数、测评集和可展开的 bundle 文件树与文件内容。
- 变体页用 tag 约束表示不同使用条件下的人为维护最优解；同一组 tag 再次上传会追加该变体的历史版本，并在右侧 inspector 中用版本线展示当前版本和历史版本，可直接查看 Bundle diff 与当前版本详情。
- 测评集页只管理 case 和 case version；case 列表显示序号、case version、当前/历史状态和生命周期状态，新增或编辑 case 会生成新的 EvalSetVersion。
- 测评页只执行手工确认：选择 exact `VariantVersion + EvalSetVersion`，可查看这组版本绑定详情，左侧 case 列表用序号、状态点和数字快捷键支持扫读与快速切换，逐条标记通过/不通过，最后记录 EvalRun。
- 历史页展示 `VariantVersion`、`EvalSetVersion`、case version、artifact digest 与 eval run 证据链。
- 权限、审计、治理、promotion review 和复杂对比视图暂不暴露在 Web V4 主流程里，避免打断核心闭环。

## 快速开始

正式版工作区位于 `apps/api` 和 `apps/web-v4`。旧前端工作台、早期 demo 和 prototype 运行时代码已经从主分支移除；后续产品开发以这两个目录为准。

### 一键本地运行

```bash
bash scripts/dev.sh
```

这个命令会启动：

- API: `http://127.0.0.1:8000`
- Web V4 正式前端: `http://127.0.0.1:3030/skills`

脚本使用 `uv` 运行 Python API，并在 `apps/web-v4/node_modules` 缺失时安装前端依赖；脚本默认设置 `UV_NO_CACHE=1`，不会污染全局 Python 环境或依赖全局 uv cache 权限。
本地 API 数据默认持久化到 `.data/skillhub.sqlite3`。可以用 `SKILLHUB_DATABASE_URL` 或 `SKILLHUB_DATA_DIR` 覆盖。
本地开发默认 actor 是 `product-operator`，页面顶部操作栏会显示当前操作者。前端所有 API 请求会带上后端 session cookie；直接调 API 时仍可用 `X-SkillHub-Actor` header 模拟不同用户。后续正式认证会把开发期 actor 机制替换成真实 session/token。

启动后先检查：

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:3030/skills
```

### 手动运行

终端 1：

```bash
cd apps/api
mkdir -p ../../.data
SKILLHUB_DATABASE_URL=sqlite:///$PWD/../../.data/skillhub.sqlite3 \
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

### 新版前端单独启动

`apps/web-v4` 连接正式 Python API：

```bash
cd apps/web-v4
npm install
VITE_SKILLHUB_API_URL=http://127.0.0.1:8000 npm run dev -- --host 127.0.0.1 --port 3030
```

兼容入口 `bash scripts/dev-v4.sh` 仍可直接启动同一套正式版前端。

打开：

```bash
http://127.0.0.1:3030/skills
```

### 建议试用路径

1. 打开 `http://127.0.0.1:3030/skills`。
2. 首页可搜索 skill、owner 和 tag；点击任意 skill 进入详情页。
3. 点 `新建 Skill`，上传标准 Skill 文件夹或 zip，再输入一个或多个 tag。Skill 名称和描述优先从 `SKILL.md` frontmatter 读取，owner 使用当前本地 actor。
4. 在 `概览` 查看 Skill 根目录、维护者、状态、说明、默认变体、当前版本、验证分数、测评集，以及可展开的 bundle 文件树。点击文件名可以查看具体内容。
5. 在 `变体` 页查看 tag 组合、版本线和 bundle 文件摘要；点击 `上传版本` 会在页面内打开上传面板，默认带入当前选中变体的 tags；如果 tag 组合已存在，就是给该变体追加历史版本；如果 tag 组合不存在，就是创建新变体。
6. 在 `测评集` 页管理测试用例：点击 `添加 case` 新增用例；点击 `编辑为新版本` 会创建新的 case version，并更新当前 EvalSetVersion。
7. 在 `测评` 页选择 exact `VariantVersion + EvalSetVersion`，可点 `查看详情` 核对内容 digest、case 数和创建信息；逐条点击 `通过` 或 `不通过`，全部确认后点击 `记录本次测评`。
8. 在 `历史` 页查看 variant version、eval run、case result 的证据链。
9. 在 `导入 bundle` 或 `上传版本` 中上传以下任一来源：
   - 根目录包含 `SKILL.md` 的文件夹，或
   - 根目录文件夹包含 `SKILL.md` 的 zip。
10. `SKILL.md` 必须以 frontmatter 开头：

```markdown
---
name: security-reviewing
description: Review pull requests for auth and data access regressions.
---

# Security Reviewing
```

导入后的 bundle 会作为不可变 `skill_bundle` artifact 保存，创建出的 variant version 指向这个 artifact。
如果缺少 `SKILL.md`、frontmatter 不合法、缺少 `name`/`description`，或 zip 无法读取，页面会在导入表单顶部显示错误摘要，并把同一条错误标到文件夹或 zip 上传控件旁。

### 核心流程跑通清单

完成一次正式版手工验收时，按下面顺序检查：

| 步骤 | 页面 | 操作 | 期望结果 |
| --- | --- | --- | --- |
| 1 | Hub 首页 | 点击 `新建 Skill`，上传标准 Skill 文件夹或 zip，输入 tag；最近测评超过 6 条时点击 `查看全部` | 创建后进入 Skill 详情页；首页可搜索到该 Skill；卡片能看到维护者、当前版本和测评集版本；最近测评能展开并收起 |
| 2 | Skill 概览 | 查看 summary 身份卡；展开 bundle 文件夹并切换文件 | Summary 显示真实根目录、维护者和状态；右侧显示对应文件内容、路径和 digest，Skill 本身不显示图标 |
| 3 | 变体 | 查看右侧版本线；点击 `Bundle diff` / `查看该版本详情`；点击 `上传版本`，在页面内上传面板输入一组 tag 并上传 bundle | 新 tag 组合创建新变体；已有 tag 组合追加该变体的新版本；当前版本在线性版本历史中清晰标出；inspector 能核对当前版本 diff 与 digest |
| 4 | 测评集 | 新增 case；再编辑已有 case 为新版本 | case version 增加；当前 EvalSetVersion 更新；case 列表能按序号、版本和状态扫读；此页不执行测评 |
| 5 | 测评 | 选择 exact `VariantVersion + EvalSetVersion`，点击两个 `查看详情`，逐 case 标记通过/不通过 | 详情区显示 VariantVersion / EvalSetVersion 的真实绑定信息；case 列表显示序号、状态点和快捷键；未全部确认前不能记录；全部确认后可点击 `记录本次测评` |
| 6 | 历史 | 打开 `历史` tab，选择刚记录的 run | 展示 run、VariantVersion、EvalSetVersion、case result、artifact digest 与版本链 |

如果只做冒烟验收，至少覆盖：新建 Skill、上传/更新变体、查看 bundle、创建 case、手动测评记录、历史证据链。

### 验证命令

推送前运行：

```bash
cd apps/api
uv run pytest
```

```bash
cd apps/web-v4
npm run test
npm run e2e
npm run e2e:visual
npm run lint
npm run build
```

`npm run e2e` 会用临时 SQLite 数据库启动 API 和 Web V4，执行一次从新建 Skill 到历史证据链的正式流程冒烟。详见 [Web V4 E2E smoke](apps/web-v4/e2e/formal-flow.md)。
`npm run e2e:visual` 会用固定 seed 和 `1586x992` viewport 截取 5 个正式页面，防止 UI 布局偏离当前基线。详见 [Web V4 视觉 Smoke](apps/web-v4/e2e/visual-smoke.md)。

运行中的应用可用下面命令冒烟检查：

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:3030/skills
```

正式 API Alembic migration 位于 `apps/api/migrations`；第一版 migration 会执行
`apps/api/skillhub/infrastructure/db/schema.sql`。

## 主要文档

- [MVP spec](docs/MVP_SPEC.md)
- [API contract](docs/api-contract.md)
- [Eval result import schema](schemas/eval-result-import.schema.json)
- [Eval result import fixture](fixtures/eval-result-import.code-reviewer.json)
- [Design spec](docs/mvp-design-spec.md)
- [SQLite schema spike](docs/sqlite-schema-spike.md)
- [Storage adapter contract](docs/storage-adapter-contract.md)
- [Formal tech stack](docs/formal-tech-stack.md)
- [Formal architecture v0.1](docs/formal-architecture-v0.1.md)
- [Formal UI design v0.1](docs/formal-ui-design.md)
- [Web V4 E2E smoke](apps/web-v4/e2e/formal-flow.md)
- [Web V4 视觉 Smoke](apps/web-v4/e2e/visual-smoke.md)
- [Web V4 最终目标验收审计](docs/formal-web-v4-final-goal-audit-2026-05-22.md)
- [Web V4 视觉参考验收记录](docs/formal-web-v4-visual-reference-acceptance-2026-05-22.md)
- [Web V4 参考图差异清单](docs/formal-web-v4-reference-diff-2026-05-22.md)
- [Web V4 正式版发布范围](docs/formal-web-v4-release-scope-2026-05-22.md)
- [Web V4 代码清理审计](docs/formal-web-v4-codebase-cleanup-2026-05-22.md)
- [Product completion audit](docs/product-completion-audit-2026-05-08.md)
- [Bundle diff workbench design](docs/superpowers/specs/2026-05-08-bundle-diff-workbench-design.md)
- [Roadmap](docs/roadmap.md)
- [1.0 architecture review](docs/architecture-review-1.0.md)
- [Ralph Loop 运行说明](RALPH.md)

## Ralph Loop

项目已安装 Ralph Loop 配置，任务定义在 `.agent/tasks.json` 和 `.agent/tasks/`。

当前 promotion review、run-to-run comparison、accepted verification、skill capabilities、variant 写入字段校验、本地登录门禁和身份引用字段格式校验的后端契约与前端体验已经接入；accepted verification note、promotion decision note 和 variant/version 说明都有 1000 字符服务端上限和字段级错误回填。本地登录门禁只是开发期 session gate，身份引用格式校验也不是最终 identity store 或 OIDC/JWT。后续 Ralph 任务应继续围绕真实认证、产品打磨、文档审计和回归覆盖推进。

运行前需要 Docker Sandboxes 登录：

```bash
sbx login
```

如果使用项目本地下载的 `sbx` 二进制：

```bash
PATH="$PWD/.tools/sbx/bin:$PATH" ./ralph.sh --agent codex
```

当前 Codex 沙箱里需要把 `sbx` 状态写到可写目录：

```bash
HOME=/private/tmp/skillhub-sbx-home PATH="$PWD/.tools/sbx/bin:$PATH" sbx login
HOME=/private/tmp/skillhub-sbx-home PATH="$PWD/.tools/sbx/bin:$PATH" ./ralph.sh --agent codex
```

如果只想验证一轮：

```bash
PATH="$PWD/.tools/sbx/bin:$PATH" ./ralph.sh --agent codex --once
```
