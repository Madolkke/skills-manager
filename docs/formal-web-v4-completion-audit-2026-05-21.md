# SkillHub Web V4 正式版完成度审计

日期：2026-05-21
最近更新：2026-05-22

最终状态：2026-05-22 已完成最终目标验收，权威结论见 `docs/formal-web-v4-final-goal-audit-2026-05-22.md`。后续清理又移除了旧 `apps/web`、早期 `demo`、`demo-backend` 和 `prototype` 运行时代码，清理记录见 `docs/formal-web-v4-codebase-cleanup-2026-05-22.md`。下方原始审计保留为收口过程记录，其中“不要标记总目标完成”的旧结论已被最终目标验收审计替代。

结论：**不要标记总目标完成。** Web V4 已经跑通正式版核心闭环，并且默认启动入口已经切到 `apps/web-v4`；后续补充了仓库内 Playwright E2E smoke 和 5 页视觉 smoke，把临时真实操作与当前 UI 基线固化为可重复验证。2026-05-22 继续收敛了概览页术语、概览 summary 视觉重心、主操作边界、case 版本路线图、测评集列表工具条、手动测评操作条、测评集死入口、全局 rail、变体上传上下文、变体 inspector 版本线、变体 inspector 底部动作、Hub 首页信息密度、最近测评全量入口、bundle tree 层级、测评集 case 列表密度、手动测评 case 列表密度、手动测评进度区比例和手动测评版本详情入口：bundle 文件树以真实 Skill slug 作为根目录，已从平铺分组收敛为可展开的根目录、子目录和文件叶子树，summary 左侧用真实根目录、维护者和状态组成身份信息 tile，在不恢复 Skill 图标的前提下补足视觉重心，版本入口改成不夸大能力边界的 `版本管理`，`上传版本` 只出现在概览和变体这两个 bundle 版本上下文，变体页上传已从居中 modal 改为页面内侧卡并默认带入当前选中变体 tags，变体 inspector 已把版本历史从纵向卡片改为水平 version line 和当前版本摘要，并补充文件级 `Bundle diff` 与当前 VariantVersion 详情动作，case 版本历史按 v1 到当前版本顺序展示为带 marker 和连接线的横向 roadmap，并提示下一版待创建，case 列表提供搜索、状态筛选和排序控件，列表行用真实 position、case version、当前/历史状态和 lifecycle status 提升扫读密度，手动测评列表行用状态点、`#position`、case version、结果状态和数字快捷键提升扫读密度，并修复 0-based position 导致第二条显示为 1 的问题，手动测评进度区改为“摘要卡 + 结果统计 + 结果分布条”的三段式布局，手动测评 selector 旁的 `查看详情` 能展开 VariantVersion / EvalSetVersion 真实绑定详情，手动测评底部操作条对齐当前 case 详情面板，测评集侧栏移除了没有菜单和 handler 的更多按钮，左侧 rail 只保留有真实行为的首页、搜索、新建和折叠入口，顶部 actor 改为静态身份标识；Hub 卡片在不恢复 Skill 图标的前提下补充维护者、更新时间和得分胶囊，右侧最近测评行补充当前版本、测评集版本、操作者和时间，并把 `查看已验证` 筛选命令替换成真实的 `查看全部` / `收起` 本地列表展开。测评集、测评、历史页不再暴露不相关的变体上传动作；跨 Skill 全量测评历史页不纳入当前 5 图正式版范围，避免把参考图外能力伪装成成熟主流程。正式版 release PR #1 已合并到 `main`，merge commit 为 `add9620af4d43cd8544dff0fe50f741c9c164f83`，合并前 GitHub Actions 全部通过；合并后已完成本地 lint/build/unit/E2E/视觉 smoke/API pytest 和 agent-browser 默认入口验证；视觉参考验收记录已把 5 张参考图和当前截图基线按产品范围逐页验收。剩余未收口项主要是原开发工作树里的旧 `apps/web` 脏改动仍需归档、迁移或明确丢弃，以及后续能力不应在当前 UI 中伪造。

## 审计输入

- 目标范围：当前线程目标中列出的 5 张参考图、核心 Skill/Variant/EvalSet/Manual Eval/History 流程、交互约束和工程约束。
- 参考图：`docs/product-ui-reference/01-hub-home.png` 到 `05-variant-management.png`。
- 视觉参考验收：`docs/formal-web-v4-visual-reference-acceptance-2026-05-22.md`。
- 参考差异清单：`docs/formal-web-v4-reference-diff-2026-05-22.md`。
- 发布范围：`docs/formal-web-v4-release-scope-2026-05-22.md`。
- 旧工作台范围审计：`docs/legacy-web-worktree-audit-2026-05-22.md`。
- 当前正式代码：`apps/web-v4`、`apps/api`、`scripts/dev.sh`、`README.md`。
- 最近一组正式版提交覆盖 Web V4 新建、首页、概览、变体、测评集、手动测评、历史证据链、默认入口、手动测评操作条修正、正式流程 E2E、5 页视觉 smoke、白底扁平化 Hub 外壳、Hub 信息密度、bundle tree 层级、变体 inspector 版本线、case 版本路线图和变体上传上下文化。
- 工作树范围：正式版发布分支只审计和提交 `apps/web-v4`、`apps/api`、`docs`、`README.md` 和相关脚本；原开发工作树里的旧 `apps/web` 历史脏改动和未跟踪文件已单独记录，但未纳入正式版完成证据。

## 逐项要求审计

| 要求 | 当前证据 | 判定 |
| --- | --- | --- |
| 默认使用正式版入口 | `scripts/dev.sh` 已分发到 `scripts/dev-v4.sh`；README 一键启动改为 `bash scripts/dev.sh`，Web V4 默认端口 `3030`。 | 已证明 |
| 保留旧工作台但不作为主流程 | `scripts/dev-legacy-web.sh` 保留旧 `apps/web` 入口；README 明确旧工作台只用于对照。 | 已证明 |
| 5 张设计图作为目标参考 | `docs/product-ui-reference/` 中 5 张图存在；Web V4 页面结构分别对应 Hub、概览、测评集、手动测评、变体；`docs/formal-web-v4-visual-reference-acceptance-2026-05-22.md` 已按当前产品范围逐页验收。 | 已证明 |
| Skill 不需要图标 | Web V4 Skill 卡片和概览主标题不依赖 Skill 图标；侧栏只有产品级 `SH` 标识。 | 已证明 |
| Hub 首页可新建 Skill | `HubPage` 提供 `新建 Skill`；`NewSkillModal` 只要求 tag 与 bundle 上传。Playwright 临时脚本已真实创建 Skill。 | 已证明 |
| Hub 首页信息密度 | `HubPage` Skill 卡片显示维护者、更新时间、得分胶囊、tags 和三项核心指标；最近测评行显示 Skill、得分、当前版本、测评集版本、操作者和时间，超过 6 条时可在同一真实列表内 `查看全部` / `收起`。 | 已证明 |
| 上传标准 Skill 文件夹 | `BundlePicker` 支持 `folder_files`；`sourceFromFiles` 生成 `files` payload；API 测试覆盖 folder import。 | 已证明 |
| 上传 zip | `BundlePicker` 支持 `zip_file`；`sourceFromFiles` 生成 `zip_base64`；README 记录 folder/zip 两条路径。 | 已证明 |
| Skill 名称/说明来自 `SKILL.md` | `NewSkillModal` 调 `api.importSkill`，后端 `parse_skill_import_source` 读取 frontmatter；README 写明 name/description 要求。 | 已证明 |
| 通过 tags 创建或更新变体 | `VariantUploadForm` 使用 `sameTags` 判断：同 tags 创建 `VariantVersion`，新 tags 创建 `Variant`；变体页页面内上传面板默认带入当前选中变体 tags，概览页仍可用 modal 上传；右侧 inspector 用水平 version line 展示当前版本和历史版本，并提供当前版本 `Bundle diff` 与 VariantVersion 详情。 | 已证明 |
| 查看 bundle 文件内容 | `OverviewPage` 使用 `BundleBrowser` 展示可展开的 bundle 文件树与内容；summary 身份 tile 显示真实根目录、维护者和状态；文件树根目录显示真实 Skill slug，子目录和文件叶子有独立 branch/leaf 节点，真实流程截图覆盖 `SKILL.md` 和 references。 | 已证明 |
| 管理测评集和 case version | `EvalSetsPage` 新增 case、编辑为新版本；`CaseVersionRoadmap` 按 v1 到当前版本展示连接式 case version roadmap，并显示下一版待创建；API 会生成新的 `EvalSetVersion`。 | 已证明 |
| 测评集列表可扫读和可整理 | `EvalSetsPage` case 列表提供搜索、全部/活跃筛选和 `Case 排序` 下拉，可按列表顺序、标题或版本号整理；每行展示 `#position`、`case vN`、当前/历史状态和 lifecycle status。 | 已证明 |
| 测评集管理不混入测评执行 | `EvalSetsPage` 只管理 case；`EvaluatePage` 独立执行人工测评。 | 已证明 |
| 测评集页没有无动作入口 | `EvalSetsPage` 已移除侧栏里没有菜单和 handler 的 `更多测评集操作` 按钮；当前可见控件都对应真实筛选、排序、新增、编辑或复制动作。 | 已证明 |
| 测评集和测评页不暴露不相关主操作 | `SkillPage` 只在 `overview` 和 `variants` tab 显示 `上传版本`；测评集、测评和历史页顶部不再出现变体上传入口。 | 已证明 |
| 独立测评页选择 exact `VariantVersion + EvalSetVersion` | `EvaluatePage` 顶部两个 selector 绑定具体版本 ID，`recordEvalRun` 发送 exact IDs；selector-local `查看详情` 展示选中 VariantVersion / EvalSetVersion 的变体、版本、创建者、内容 digest、bundle 文件数和 case 数。 | 已证明 |
| 逐 case 手动标记通过/不通过 | `EvaluatePage` 支持 pass/fail、下一条、键盘 `P/F/N/S`；左侧列表显示状态点、`#position`、case version、结果状态和数字快捷键；结果存入 `results`。 | 已证明 |
| 未全部确认前不能记录 | `canRecord` 要求 `summary.pending === 0` 且有 cases；按钮禁用态和提示由 `manualRecordHint` 控制。 | 已证明 |
| 手动测评操作条属于当前 case 详情区 | `eval-action-bar` 在桌面端左侧对齐 `manual-case-detail`，不再横跨或遮挡左侧 case 列表；移动端回退为普通流式宽度。 | 已证明 |
| 记录测评结果 | `api.recordEvalRun` 记录 `manual_pass_fail`；临时 Playwright 已记录 run 并进入历史页验证。 | 已证明 |
| 查看历史版本和证据链 | `HistoryPage` 展示 run、`VariantVersion`、`EvalSetVersion`、case result、input/expected digest、版本链。 | 已证明 |
| 主流程隐藏权限、审计、治理、危险区 | `rg` 在 `apps/web-v4/src` 中未发现主流程 UI 暴露权限/审计/治理/危险区；README 明确 Web V4 暂不暴露这些功能。 | 已证明 |
| 不让用户填写无意义字段 | 新建 Skill 只填 tag 和 bundle；上传版本只填 tag 和 bundle；case 表单只填 title/input/expected/notes。 | 已证明 |
| 不用跳转页面下方冒充导航 | Web V4 使用 `SkillTabs` 和 URL query tab 导航；未把测评/历史藏在同页锚点下方。 | 已证明 |
| 全局 rail 不暴露无行为控件 | `BrandRail` 只保留首页、搜索、新建 Skill 和折叠；搜索会回到 Hub 并聚焦搜索框，未实现的全局测评记录、历史、设置入口不再显示；`TopBar` 的 actor 从按钮改为静态身份标识。 | 已证明 |
| 组件成熟、层次清楚、低心智负担 | 已有较清晰的 rail/topbar/tabs/card/inspector/action bar；手动测评遮挡问题已修，进度区按摘要、统计和分布拆成三段；概览页主操作改为 `版本管理`；bundle tree 改为可展开层级树；变体页上传改为上下文侧卡，inspector 版本历史改为线性 version track，底部动作改为文件级 diff 与版本详情，减少上传时离开当前变体信息的心智切换；Hub 首页卡片、最近测评行和最近测评展开入口的扫读信息已补足。 | 部分证明 |
| 严格向参考图看齐 | 最近几轮已按参考图逐页打磨；`npm run e2e:visual` 用固定 seed 截取 5 页当前 Web V4 基线并断言关键结构；`docs/formal-web-v4-reference-diff-2026-05-22.md` 已记录逐图差异和后续优先级；`docs/formal-web-v4-visual-reference-acceptance-2026-05-22.md` 已记录参考图验收口径和接受偏差。 | 已证明 |
| 避免继续堆叠 demo 债务 | Web V4 从旧 `apps/web` 分离，文件大多在 200-300 行；手动测评列表样式已从 `manual-evaluation.css` 拆到 `manual-case-list.css`；手动测评进度区抽成 `ManualProgressPanel`；`workspaces.css` 283 行已接近上限。 | 部分证明 |
| 所有用户可见文档默认中文 | README 与本审计为中文；代码标识保留英文。 | 已证明 |
| 每轮修改后类型/单元/后端/真实操作验证 | 最近几轮均执行 `npm run build`、`npm run test`、`npm run lint`、`uv run pytest` 和真实操作验证；后续已补充 `apps/web-v4` 的 `npm run e2e` 与视觉 smoke。 | 已证明 |
| README 一键启动和核心流程说明 | README 已包含 `bash scripts/dev.sh`、health check、建议试用路径、核心流程跑通清单。 | 已证明 |
| 阶段性稳定后推送 GitHub | clean release 分支 `release/formal-skillhub-v4` 已推送；PR #1 已 squash merge 到 `main`，merge commit 为 `add9620af4d43cd8544dff0fe50f741c9c164f83`；合并范围排除旧 `apps/web`、`apps/web-v2`、`apps/web-v3` 实验路径；合并前 GitHub Actions 4 个 job 全部通过。 | 已证明 |

## 当前最重要的缺口

1. **参考图差异和验收口径已固化，当前 5 图主流程的阻塞差距已关闭。** `docs/formal-web-v4-reference-diff-2026-05-22.md` 记录了 5 张参考图和当前 baseline 的差距；`docs/formal-web-v4-visual-reference-acceptance-2026-05-22.md` 记录了逐页验收结论、接受偏差和不伪造范围。变体上传上下文化、变体 inspector 版本线、变体 inspector 底部动作、测评集版本路线图、Hub 卡片密度、最近测评层级、最近测评全量入口、bundle tree 层级、Skill 概览 summary 视觉重心、测评集 case 列表密度、手动测评 case 列表密度、手动测评进度区比例和手动测评版本详情入口已关闭。跨 Skill 全量测评历史页已明确为未来独立范围，不纳入当前 5 图正式版收口。
2. **旧 `apps/web` 脏改动会持续制造范围混淆。** `docs/legacy-web-worktree-audit-2026-05-22.md` 已记录原开发工作树中旧工作台脏改动的归属、风险和处理选项；本正式版发布分支明确排除旧 `apps/web` redesign，最终仍需决定这些旧改动要么归档、要么迁移、要么明确丢弃。
3. **Visual polish 仍有未来扩展项。** 更深的逐行 bundle diff、跨 Skill 全量测评历史页、case tags 和多测评集列表都需要独立信息架构或后端字段支持后再做，当前正式版不伪造这些入口。

## 下一步建议

优先级最高的是把正式版范围和发布路径收口：

1. 处理旧 `apps/web` 脏改动，避免正式版和历史工作台继续互相干扰。
2. 如果后续要做跨 Skill 全量测评历史页、逐行 bundle diff、case tags 或多测评集列表，先写独立信息架构和后端字段方案，不在当前 5 图正式版里伪造入口。

## 本轮验证记录

本审计文档写入后已执行：

```bash
cd apps/web-v4 && npm run lint
cd apps/web-v4 && npm run build
cd apps/web-v4 && npm run test
cd apps/web-v4 && npm run e2e
cd apps/web-v4 && npm run e2e:visual
cd apps/api && uv run pytest
git diff --check -- README.md docs apps/web-v4
```

结果：

- Web lint：通过。
- Web build/typecheck：通过。
- Web unit：1 个测试文件、10 个测试通过。
- Web E2E：1 条 Playwright 正式主流程通过。
- Web 视觉 smoke：5 页截图基线通过，截图尺寸为 `1586x992`。
- API pytest：115 passed。
- `git diff --check`：通过。
- 默认入口 smoke：`SKILLHUB_API_PORT=18085 SKILLHUB_WEB_PORT=13036 SKILLHUB_DATA_DIR=/tmp/skillhub-audit-final-data bash scripts/dev.sh` 启动 Web V4；`curl /health` 返回 `{"ok":true}`；Web `/skills` 返回 200；Playwright 打开 `http://127.0.0.1:13036/skills`，确认页面包含 `SkillHub` 和 `新建 Skill`，console error/warn 为空，截图保存到 `/tmp/skillhub-audit-final-v4.png`。

2026-05-22 补充验证：

- 参考资料：实现前再次检查 shadcn Sidebar、shadcn Dashboard Blocks 和 Radix Dialog 文档，用成熟 sidebar/card/dialog 模式约束本轮概览改动。
- agent-browser 真实操作：临时启动 `scripts/dev.sh`，导入一个标准 Skill bundle，打开 `http://127.0.0.1:13092/skills?skill=...`，确认页面按钮为 `版本管理` / `打开历史`，bundle 根目录为 `code-reviewer/`，分组为 `根目录文件` 与 `references/`。
- Playwright 视觉基线：`npm run e2e:visual -- --update-snapshots=all` 更新 `02-skill-overview-chromium-darwin.png`，后续 `npm run e2e:visual` 通过。
- 顺序运行注意：`npm run e2e` 和 `npm run e2e:visual` 共用默认测试端口，不应并行运行；本轮并行触发过一次 `18110` 端口占用，随后顺序重跑 `npm run e2e` 通过。

2026-05-22 变体上传上下文补充验证：

- 参考资料：实现前检查 Carbon File uploader 和 Atlassian file upload / media picker 相关模式，确认多文件或 bundle 上传更适合页面内上下文区域，不继续用居中 modal 打断变体详情。
- TDD 记录：先把 `apps/web-v4/e2e/helpers.ts` 改为期望变体页没有 `上传版本` dialog，而是出现 `.variant-upload-panel`；`npm run e2e -- e2e/formal-flow.spec.ts` 先失败，失败点为仍存在 `dialog`。实现页面内上传面板后同一命令通过。
- Web lint/build/unit/API：`npm run lint`、`npm run build`、`npm run test`、`cd apps/api && uv run pytest` 均通过；unit 为 1 个测试文件、8 个测试，API 为 115 passed。
- Web E2E：`npm run e2e` 通过，正式流程使用页面内变体上传面板追加 `VariantVersion`。
- Web 视觉 smoke：先用 `npm run e2e:visual -- --update-snapshots=all` 更新 `05-variant-management-chromium-darwin.png`，让变体页基线包含打开的上传面板；随后 `npm run e2e:visual` 通过。
- agent-browser 真实操作：临时启动 Web V4，导入 `Agent Browser Panel` Skill，打开变体页，点击 `上传版本` 后确认 `.variant-upload-panel` 出现且预置 `codex` / `gpt5.4` tags；上传 zip 后提交，页面从 `当前 v1` 更新为 `当前 v2`，上传面板关闭。

2026-05-22 测评集版本路线图补充验证：

- 参考资料：实现前检查 Carbon Progress Indicator、Atlassian Progress Tracker 和 Material Stepper，确认版本链应有 step 状态、连接线、标签和辅助信息，而不是彼此孤立的卡片。
- TDD 记录：先把正式流程 E2E 改为要求 `.case-version-track`、`.case-version-step`、当前 step 的 `aria-current="step"` 和待创建 step；`npm run e2e -- e2e/formal-flow.spec.ts` 先失败，失败点为找不到 `.case-version-track`。实现 `CaseVersionRoadmap` 后同一命令通过。
- 工程约束：新增 `apps/web-v4/src/components/CaseVersionRoadmap.tsx`，并把 roadmap 样式拆到 `apps/web-v4/src/styles/case-version-roadmap.css`；`EvalSetsPage.tsx` 保持在 200 行以内，`evaluation.css` 回落到 209 行。
- Web 视觉 smoke：`npm run e2e:visual -- --update-snapshots=all` 更新 `03-eval-set-management-chromium-darwin.png`，新的基线显示带 marker 和连接线的 case version roadmap。
- 完整验证：`npm run lint`、`npm run build`、`npm run test`、`npm run e2e`、`npm run e2e:visual`、`cd apps/api && uv run pytest` 均通过；unit 为 1 个测试文件、8 个测试，API 为 115 passed。
- agent-browser 真实操作：临时启动 Web V4，导入 `Case Roadmap Skill`，通过 API 创建并更新 case 到 v2，打开测评集页；页面存在 `.case-version-track`，`.case-version-step` 数量为 3，当前 step 文本包含 `v2（当前）`，待创建 step 文本包含 `v3` 和 `待创建`。

2026-05-22 Hub 信息密度补充验证：

- 参考资料：实现前检查 Carbon Tile、PatternFly Data list 和 Atlassian 组件/组合文档，采用“卡片内关键元数据 + 列表行内版本/状态/操作者”的信息层级，不恢复产品目标明确排除的 Skill 图标。
- TDD 记录：先把视觉 smoke 改为要求首页首个 `.skill-card` 包含 `维护者 product-operator`，首个 `.recent-row` 包含 `Primary v\d+` 和 `操作者 product-operator`；首次 `npm run e2e:visual` 失败，失败点为卡片没有维护者元数据。实现 Hub 卡片和最近测评行后同一断言通过。
- 工程约束：`HubPage.tsx` 保持 248 行；原 `hub.css` 拆为 `hub.css`、`hub-cards.css`、`hub-recent.css`，分别保持 93、171、90 行，避免首页样式继续变成大文件。
- Web 视觉 smoke：`npm run e2e:visual -- --update-snapshots=all` 更新 `01-hub-home-chromium-darwin.png`；随后 `npm run e2e:visual` 通过。
- 完整验证：`npm run lint`、`npm run build`、`npm run test`、`npm run e2e`、`npm run e2e:visual`、`cd apps/api && uv run pytest` 均通过；unit 为 1 个测试文件、8 个测试，API 为 115 passed。
- agent-browser 真实操作：临时启动 Web V4，导入 `Hub Density Check` Skill，追加到 `v3`，创建 `Primary v2` 测评集版本并记录 100% 手动测评；打开 `http://127.0.0.1:13101/skills` 后，snapshot 显示卡片包含 `维护者 product-operator`、`测评集版本 v2`、`当前版本 v3`，最近测评行包含 `当前 v3 · Primary v2` 和 `操作者 product-operator`，`查看已验证` 入口可点击并保留已验证结果。

2026-05-22 Bundle tree 层级补充验证：

- 参考资料：实现前检查 Carbon Tree view、PatternFly Tree view 和 Atlassian 层级组件/导航文档，采用 branch/leaf、展开状态、统一文件夹/文件图标和缩进层级，不增加没有行为的工具按钮。
- TDD 记录：先把视觉 smoke 改为要求概览页存在 `.bundle-tree-node.branch` 根目录、`examples/` 子目录和 `.bundle-tree-node.leaf` 的 `pr.diff`；首次 `npm run e2e:visual` 失败，失败点为当前平铺分组实现找不到 branch 节点。随后新增 `buildBundleTree` 单元测试，首次 `npm run test` 失败，失败点为 `buildBundleTree is not a function`。
- 工程约束：新增 `BundleTreeNode` / `buildBundleTree`，`BundleBrowser` 渲染可折叠树；相关文件行数保持在 300 行以内。
- Web 视觉 smoke：`npm run e2e:visual -- --update-snapshots=all` 更新 `02-skill-overview-chromium-darwin.png`；新基线展示 `code-reviewer/` 根目录、`examples/`、`references/`、`tests/` 子目录和文件叶子。
- 完整验证：`npm run lint`、`npm run build`、`npm run test`、`npm run e2e`、`npm run e2e:visual`、`cd apps/api && uv run pytest` 均通过；unit 为 1 个测试文件、9 个测试，API 为 115 passed。
- agent-browser 真实操作：临时启动 Web V4，导入 `Tree Polish Check` Skill，打开概览页；snapshot 显示 `tree-polish-check/` 根目录、`examples/` 子目录和 `pr.diff` 文件叶子。通过键盘聚焦 `examples/` 并按 Space 后，`aria-expanded` 从 `true` 变为 `false` 且 `pr.diff` 不再显示；再次展开后聚焦 `pr.diff` 并按 Enter，内容区标题变为 `examples/pr.diff`。

2026-05-22 变体 inspector 版本线补充验证：

- 参考资料：实现前检查 Carbon Progress indicator、PatternFly Progress stepper 和 Atlassian Progress tracker，采用节点、连接线、当前态和简短摘要的线性版本表达，不补未成熟 `Bundle diff` / detail 动作。
- TDD 记录：先把视觉 smoke 改为要求变体 inspector 出现 `.inspector-version-track`、当前 `.version-track-step.current`、`.version-current-summary`，并要求 `.timeline-item` 数量为 0；首次 `npm run e2e:visual` 失败，失败点为找不到 `.inspector-version-track`。
- 工程约束：新增 `VariantVersionTrack` 组件和 `variant-version-track.css`，`VariantsPage.tsx` 与 `workspaces.css` 保持在 300 行以内。
- Web 视觉 smoke：`npm run e2e:visual -- --update-snapshots=all` 更新 `05-variant-management-chromium-darwin.png`；新基线显示 inspector 中的水平 v3/v2/v1 版本线和当前版本摘要。
- 完整验证：`npm run lint`、`npm run build`、`npm run test`、`npm run e2e`、`npm run e2e:visual`、`cd apps/api && uv run pytest` 均通过；unit 为 1 个测试文件、9 个测试，API 为 115 passed。
- agent-browser 真实操作：临时启动 Web V4，导入 `Variant Track Check` Skill 并追加到 v3，打开变体页；snapshot 显示 `版本历史`、`Bundle 内容` 和当前变体，DOM 检查显示 `.inspector-version-track` 文本为 `v3当前v22026/05/21v12026/05/21`，`.version-current-summary` 包含 `当前 v3`，`.variant-detail-panel .timeline-item` 数量为 0。

2026-05-22 测评集 case 列表密度补充验证：

- 参考资料：实现前检查 Carbon Data table、PatternFly Data list 和 PatternFly Status，采用“数据列表行 + 紧凑元信息胶囊 + 明确状态文本”的表达；后端不支持 case tags，因此不伪造参考图里的 tags。
- TDD 记录：先把视觉 smoke 改为要求测评集页首个 `.case-row` 包含 `.case-position-mark`、`.case-row-metadata`、`.case-current-chip` 和 `.case-status-chip`；首次 `npm run e2e:visual` 失败，失败点为找不到 `.case-position-mark`。实现后 `npm run e2e:visual` 通过。
- 工程约束：`EvalSetsPage.tsx` 为 216 行，`evaluation.css` 为 278 行，均保持在 300 行以内；case 行只使用真实 `position`、`case_version.version_number`、`case.current_version_id` 和 `case.lifecycle_status`。
- Web 视觉 smoke：`npm run e2e:visual -- --update-snapshots=all` 更新 `03-eval-set-management-chromium-darwin.png`；为避免无关截图字节漂移，只保留测评集页截图变化。
- 完整验证：`npm run lint`、`npm run build`、`npm run test`、`npm run e2e`、`npm run e2e:visual`、`cd apps/api && uv run pytest` 均通过；unit 为 1 个测试文件、9 个测试，API 为 115 passed。
- agent-browser 真实操作：临时启动 `scripts/dev.sh` 到 `18104/13104`，导入 `Case Density Check` Skill，创建 5 个 case 并把首个 case 更新到 v2；打开测评集页后，snapshot 显示首个按钮为 `PR: missing owner filter，#1，case v2，当前版本，活跃`。聚焦第二个 case 行并按 Enter 后，URL 切到第二个 case，详情标题变为 `PR: tenant scope not enforced`，active 行为 `#2PR: tenant scope not enforcedcase v1当前活跃`。

2026-05-22 手动测评 case 列表密度补充验证：

- 参考资料：实现前检查 Carbon Structured list、PatternFly Data list 和 Material lists，采用 compact row、状态点、主文本、辅助元信息和快捷键的组合；列表只展示真实 case position、case version 和人工测评结果。
- TDD 记录：先把视觉 smoke 改为要求手动测评页首个 `.manual-case-row` 包含 `.manual-case-index`、`.manual-status-dot.passed` 和 `.manual-shortcut-chip`，并要求第二行 index 为 `#2`；首次 `npm run e2e:visual` 失败，失败点为找不到 `.manual-case-index`。实现后同一命令通过。
- 工程约束：修复 `item.position || index + 1` 导致后端 0-based position 下第二条显示为 1 的问题，改为 `position + 1`；手动测评列表样式拆到 `manual-case-list.css`，`manual-evaluation.css` 回落到 211 行。
- Web 视觉 smoke：`npm run e2e:visual -- --update-snapshots=all` 更新 `04-manual-evaluation-chromium-darwin.png`；为避免无关截图字节漂移，只保留手动测评页截图变化。
- 完整验证：`npm run lint`、`npm run build`、`npm run test`、`npm run e2e`、`npm run e2e:visual`、`cd apps/api && uv run pytest` 均通过；unit 为 1 个测试文件、9 个测试，API 为 115 passed。
- agent-browser 真实操作：临时启动 `scripts/dev.sh` 到 `18105/13105`，导入 `Manual Case Density Check` Skill 并创建 4 个 case；打开手动测评页后，snapshot 显示 case 行的 accessible label 包含 `#1`、`#2` 和 `case v1`。点击 `通过` 后，DOM 检查显示第一行 `manual-status-dot passed`、index `#1`、shortcut `1`，第二行 index `#2`、shortcut `2`；按数字 `2` 后，详情标题变为 `PR: tenant scope not enforced`。

2026-05-22 手动测评进度区比例补充验证：

- 参考资料：实现前检查 Carbon Progress bar、PatternFly Progress 和 Atlassian Progress tracker，采用可量化进度条、清晰摘要和结果状态分组；人工测评是用户逐条确认，因此保留环形确认率和分布条并列，而不是用加载态。
- TDD 记录：先把视觉 smoke 改为要求手动测评页出现 `.progress-summary-card`、`.progress-total-label` 和 `.progress-track-card`，首次 `npm run e2e:visual` 失败，失败点为找不到 `.progress-summary-card`。实现三段式进度区后同一断言通过，随后截图差异按视觉基线更新。
- 工程约束：新增 `ManualProgressPanel`，把进度区从 `EvaluatePage.tsx` 中抽出；`EvaluatePage.tsx` 回落到 262 行，`ManualEvaluationPanels.tsx` 为 138 行，`manual-evaluation.css` 为 250 行。
- Web 视觉 smoke：`npm run e2e:visual -- --update-snapshots=all` 更新 `04-manual-evaluation-chromium-darwin.png`；为避免无关截图字节漂移，只保留手动测评页截图变化。
- 完整验证：`npm run lint`、`npm run build`、`npm run test`、`npm run e2e`、`npm run e2e:visual`、`cd apps/api && uv run pytest` 均通过；unit 为 1 个测试文件、9 个测试，API 为 115 passed。
- agent-browser 真实操作：临时启动 `scripts/dev.sh` 到 `18106/13106`，导入 `Progress Panel Check` Skill 并创建 4 个 case，打开测评页并点击 `通过`；DOM 检查确认 `.progress-summary-card` 文本包含 `1/4 已确认` 与 `共 4 个 case`，`.progress-track-card` 文本包含 `结果分布` 和 `25%`，统计区为 `1通过0不通过3待评估`，首行 accessible label 变为 `PR: missing owner filter，#1，case v1，通过`。

2026-05-22 Hub 最近测评全量入口补充验证：

- 参考资料：实现前检查 PatternFly Data list、PatternFly Actions 和 Atlassian Link button，采用组件内动作影响组件内列表的方式；`查看全部` 是列表展开，不伪造跨 Skill 全局历史导航。
- TDD 记录：先把视觉 smoke 改为要求 Hub 最近测评默认 `显示 6 / 7 条`，点击 `查看全部最近测评` 后变为 `显示 7 / 7 条`，再点击 `收起最近测评` 回到 `显示 6 / 7 条`；首次 `npm run e2e:visual` 失败，失败点为 `.recent-list` 没有对应 `aria-label` 且没有查看全部按钮。实现后同一命令通过。
- 工程约束：`HubPage.tsx` 为 251 行，`visual-seed.ts` 为 256 行，`hub-recent.css` 为 95 行，均保持在 300 行以内；最近测评只使用真实 `SkillSummary.latest_accepted_eval_run`，默认截断 6 条，超过 6 条时展开同一列表。
- 文档更新：`README.md`、`apps/web-v4/e2e/visual-smoke.md` 和 `docs/formal-web-v4-reference-diff-2026-05-22.md` 已同步记录最近测评可展开入口。
- 完整验证：`npm run lint`、`npm run build`、`npm run test`、`npm run e2e`、`npm run e2e:visual`、`cd apps/api && uv run pytest`、`git diff --check -- README.md docs apps/web-v4` 均通过；unit 为 1 个测试文件、9 个测试，API 为 115 passed。
- agent-browser 真实操作：临时启动 `scripts/dev.sh` 到 `18107/13107`，通过 API 创建 7 个带 EvalRun 的 Skill，打开 Hub 首页后确认右栏默认按钮为 `查看全部`、`.recent-list` 为 `最近测评，显示 6 / 7 条` 且 `.recent-row` 数量为 6；点击 `查看全部` 后变为 `收起`、`显示 7 / 7 条` 且行数为 7；再次点击后回到 `查看全部`、`显示 6 / 7 条` 且行数为 6。

2026-05-22 Skill 概览 summary 视觉重心补充验证：

- 参考资料：实现前检查 Carbon Tile、PatternFly Card 和 Atlassian Lozenge / Badge 模式，采用真实身份元数据 tile + 胶囊值的方式增强 summary，而不是恢复参考图里的 Skill 图标。
- TDD 记录：先把视觉 smoke 改为要求概览页 `.skill-identity-card` 包含 `根目录`、`code-reviewer/`、`维护者` 和 `product-operator`；首次 `npm run e2e:visual` 失败，失败点为找不到 `.skill-identity-card`。实现身份 tile 后结构断言通过，随后只更新 `02-skill-overview-chromium-darwin.png`。
- 工程约束：`OverviewPage.tsx` 为 133 行，`skill.css` 为 210 行，`responsive.css` 为 193 行，均保持在 300 行以内；summary 身份 tile 只展示真实 `skill.slug`、`skill.owner_ref` 和 `skill.lifecycle_status`，不暴露权限、审计、治理或假图标。
- 文档更新：`README.md`、`apps/web-v4/e2e/visual-smoke.md` 和 `docs/formal-web-v4-reference-diff-2026-05-22.md` 已同步记录 summary 身份信息。
- 完整验证：`npm run lint`、`npm run build`、`npm run test`、`npm run e2e`、`npm run e2e:visual`、`cd apps/api && uv run pytest`、`git diff --check -- README.md docs apps/web-v4` 均通过；unit 为 1 个测试文件、9 个测试，API 为 115 passed。
- agent-browser 真实操作：临时启动 `scripts/dev.sh` 到 `18108/13108`，通过 API 导入 `overview-identity-check` Skill，打开概览页；snapshot 显示标题、`Skill bundle`、`版本管理` / `打开历史` 和 bundle tree。DOM 检查确认 `.skill-identity-card` 文本为 `根目录 overview-identity-check/ 维护者 product-operator 状态 活跃`，`.summary-value-chip` 为 `codex + gpt5.4`，bundle 根目录为 `overview-identity-check/`，leaf 数量为 3。

2026-05-22 手动测评版本详情入口补充验证：

- 参考资料：实现前检查 [PatternFly Expandable section](https://www.patternfly.org/components/expandable-section/)、[Atlassian Inline dialog](https://atlassian.design/components/inline-dialog/) 和 [Carbon Inline notification](https://carbondesignsystem.com/components/notification/usage/#inline-notifications)，采用 selector-local detail panel，不新建假详情页。
- TDD 记录：先把视觉 smoke 改为要求两个 `查看详情` 按钮存在，点击后 `.manual-version-detail-panel` 包含 `VariantVersion`、`内容 digest`、`EvalSetVersion` 和 `8 个 case`；首次 `npm run e2e:visual` 失败，失败点为找不到 `查看变体版本详情`。实现后同一命令通过。
- 工程约束：`EvaluatePage.tsx` 为 284 行，`ManualVersionDetailPanel.tsx` 为 87 行，`manual-version-detail.css` 为 108 行，`manual-evaluation.css` 为 250 行，`responsive.css` 为 198 行，均低于 300 行；详情只使用真实 selected VariantVersion / EvalSetVersion / EvalSetVersionDetail 数据。
- 文档更新：`README.md`、`apps/web-v4/e2e/visual-smoke.md`、`docs/formal-web-v4-reference-diff-2026-05-22.md` 和本审计已同步记录手动测评版本详情入口。
- Web 视觉 smoke：`npm run e2e:visual -- --update-snapshots=all` 更新 `04-manual-evaluation-chromium-darwin.png`；为避免无关截图字节漂移，只保留手动测评页截图变化；后续 `npm run e2e:visual` 通过。
- 完整验证：`npm run lint`、`npm run build`、`npm run test`、`npm run e2e`、`npm run e2e:visual`、`cd apps/api && uv run pytest`、`git diff --check -- README.md docs apps/web-v4` 均通过；unit 为 1 个测试文件、9 个测试，API 为 115 passed。
- agent-browser 真实操作：临时启动 `scripts/dev.sh` 到 `18109/13109`，通过 API 导入 `manual-version-detail-check` Skill，追加 v2 变体版本并创建 2 个 case；打开测评页后 snapshot 显示 `查看变体版本详情` 与 `查看测评集版本详情`。点击前者后 DOM 显示 `variantPressed: true`，面板包含 `VariantVersion`、`内容 digest`、`EvalSetVersion` 和 `2 个 case`；点击后者后 DOM 显示 `evalSetPressed: true`；点击 `关闭版本详情` 后 `.manual-version-detail-panel` 不再存在。

2026-05-22 变体 inspector 底部动作补充验证：

- 参考资料：实现前检查 [PatternFly Action list](https://www.patternfly.org/components/action-list/)、[Atlassian Button group](https://atlassian.design/components/button/button-group/) 和 [Carbon Button set](https://carbondesignsystem.com/components/button/usage/#button-set)，采用 inspector-local action group 与 inline detail panel，不跳转到未定义的 diff 工作台。
- TDD 记录：先新增单元测试要求 `summarizeBundleDiff` 能按 path/fingerprint 输出 added/changed/removed/unchanged 汇总；首次 `npm run test` 失败，失败点为缺少 `../lib/variant-diff`。同时把视觉 smoke 改为要求变体页存在 `Bundle diff` / `查看该版本详情`，点击后显示 `.variant-inspector-detail-panel`；首次 `npm run e2e:visual` 失败，失败点为找不到 `Bundle diff`。
- 工程约束：把 inspector 从 `VariantsPage.tsx` 拆到 `VariantInspector.tsx`，`VariantsPage.tsx` 从 285 行降到 205 行；`VariantInspector.tsx` 为 190 行，`variant-diff.ts` 为 73 行，`variant-inspector-actions.css` 为 139 行，`workspaces.css` 保持 283 行，均低于 300 行。
- 文档更新：`README.md`、`apps/web-v4/e2e/visual-smoke.md`、`docs/formal-web-v4-reference-diff-2026-05-22.md` 和本审计已同步记录变体 inspector 底部动作。
- Web 视觉 smoke：`npm run e2e:visual -- --update-snapshots=all` 更新 `05-variant-management-chromium-darwin.png`；为避免无关截图字节漂移，只保留变体页截图变化；后续 `npm run e2e:visual` 通过。
- 完整验证：`npm run lint`、`npm run build`、`npm run test`、`npm run e2e`、`npm run e2e:visual`、`cd apps/api && uv run pytest`、`git diff --check -- README.md docs apps/web-v4` 均通过；unit 为 1 个测试文件、10 个测试，API 为 115 passed。
- agent-browser 真实操作：临时启动 `scripts/dev.sh` 到 `18111/13111`，通过 API 导入 `variant-inspector-actions-check` Skill 并追加 v2；打开变体页后 snapshot 显示 `Bundle diff` 与 `查看该版本详情`。滚动到底部后点击 `Bundle diff`，DOM 显示 `aria-pressed=true` 且面板包含 `v2 对比 v1`、`1 变更文件`、`1 新增`、`2 未变更`；点击 `查看该版本详情` 后 DOM 显示该按钮 `aria-pressed=true`，面板包含 `VariantVersion 详情`、`内容 digest` 和 `4 个文件`；再次点击后 `.variant-inspector-detail-panel` 不再存在。

2026-05-22 当前正式范围收口补充验证：

- 范围判断：跨 Skill 全量测评历史页不属于当前 5 张参考图，也不是核心闭环必需项；当前正式版保留首页右栏本地 `查看全部` 展开和单个 Skill 内的历史证据链，避免把参考图外能力伪造成主流程。
- 文档更新：`README.md` 明确首页 `查看全部` 是右栏内列表展开；`docs/formal-web-v4-reference-diff-2026-05-22.md` 把跨 Skill 全量测评历史页降级为未来独立范围；本审计把当前 5 图主流程的阻塞差距改为已关闭。
- 完整验证：`npm run lint`、`npm run build`、`npm run test`、`npm run e2e`、`npm run e2e:visual`、`cd apps/api && uv run pytest`、`git diff --check -- README.md docs apps/web-v4` 均通过；unit 为 1 个测试文件、10 个测试，API 为 115 passed。
- agent-browser 真实操作：临时启动 `scripts/dev.sh` 到 `18112/13112`，通过 API 创建 7 个带 EvalRun 的 Skill。Hub 首页右栏默认 `.recent-list` 为 `最近测评，显示 6 / 7 条`；滚动到 `查看全部最近测评` 后点击，URL 保持 `http://127.0.0.1:13112/skills`，`.recent-list` 变为 `显示 7 / 7 条` 且按钮变为 `收起`，证明这是本地展开而非伪全局历史页。打开 `Scope History Check 1` 的 `历史` tab 后，页面显示 `历史与证据链`、`VariantVersion`、`EvalSetVersion`、`case v1`、input/expected digest 和 `1/1 通过` 测评记录。

2026-05-22 旧 `apps/web` 脏改动归属审计：

- 范围判断：旧 `apps/web` 当前仍有 redesign 脏改动和未跟踪组件，但默认 `scripts/dev.sh` 已进入 `scripts/dev-v4.sh`；legacy 入口只通过 `scripts/dev-legacy-web.sh` 或 `SKILLHUB_WEB_FLAVOR=legacy bash scripts/dev.sh` 使用。
- 文档更新：新增 `docs/legacy-web-worktree-audit-2026-05-22.md`，记录旧工作台当前脏改动范围、变更性质、风险、处理选项和正式版提交原则；README 已在旧工作台说明和主要文档中链接该审计。
- 操作边界：本轮没有 stage、提交、回退或删除任何 `apps/web` 文件；后续正式版提交仍必须显式点名路径，避免旧工作台误入发布范围。
- 完整验证：`npm run lint`、`npm run build`、`npm run test`、`npm run e2e`、`npm run e2e:visual`、`cd apps/api && uv run pytest`、`git diff --check -- README.md docs apps/web-v4` 均通过；unit 为 1 个测试文件、10 个测试，API 为 115 passed。
- agent-browser 真实操作：本机未安装全局 `agent-browser`，使用 `npx agent-browser` 并执行 `npx agent-browser install` 安装 Chrome 149 到本地缓存；临时启动默认 `scripts/dev.sh` 到 `18113/13113` 后，打开 `http://127.0.0.1:13113/skills`，snapshot 显示 Web V4 Hub 的 `SkillHub`、`新建 Skill`、筛选和排序控件；点击 `新建 Skill` 后 snapshot 显示新建 Skill 对话框、文件夹上传、zip 上传和禁用的 `创建 Skill` 按钮。

2026-05-22 clean release PR 收口验证：

- 范围判断：直接以 `redesign/formal-skillhub-ui` 开 PR 会把旧 `apps/web`、`apps/web-v2`、`apps/web-v3` 历史实验混进正式版 diff，因此从 `origin/main` 新建 `release/formal-skillhub-v4`，只组装 `apps/api`、`apps/web-v4`、`scripts`、`docs`、`README.md` 和 `.gitignore`。
- 文档更新：新增 `docs/formal-web-v4-release-scope-2026-05-22.md`，README 与本审计链接发布范围；旧 `apps/web` 审计改为记录原开发工作树状态，避免误导为 release 分支仍含旧工作台脏改动。
- 本地验证：在 clean release worktree 中执行 `npm ci`、`npm run lint`、`npm run build`、`npm run test`、`npm run e2e`、`npm run e2e:visual`、`cd apps/api && uv run pytest`、`git diff --check --cached` 和 `git diff --check -- README.md docs apps/web-v4 apps/api scripts .gitignore`，均通过；unit 为 1 个测试文件、10 个测试，API 为 115 passed。
- agent-browser 真实操作：临时启动 clean release 分支默认 `scripts/dev.sh` 到 `18114/13114`，打开 `http://127.0.0.1:13114/skills` 后 snapshot 显示 Web V4 Hub 的 `SkillHub`、`新建 Skill`、筛选和排序控件；点击 `新建 Skill` 后 snapshot 显示新建 Skill 对话框、文件夹上传、zip 上传和禁用的 `创建 Skill` 按钮。
- GitHub 状态：draft PR #1 已创建，URL 为 `https://github.com/xunx911/skills-manager/pull/1`；PR head 为 `release/formal-skillhub-v4`，base 为 `main`，`mergeStateStatus` 为 `CLEAN`；GitHub Actions 中 `Backend tests`、`Formal API domain tests`、`Demo frontend build`、`Formal web build` 四个 job 均为 `SUCCESS`；截至本审计更新时没有评论或 review。

2026-05-22 PR #1 合并状态：

- GitHub 状态：PR #1 已从 draft 转为 ready for review，随后通过 squash merge 合并到 `main`；merge commit 为 `add9620af4d43cd8544dff0fe50f741c9c164f83`。
- 合并前证据：`gh pr view 1` 显示 PR 为 open、非 draft、`mergeable=MERGEABLE`、`mergeStateStatus=CLEAN`；`Backend tests`、`Formal API domain tests`、`Demo frontend build`、`Formal web build` 四个 job 均为 `SUCCESS`。
- 合并范围：`origin/main` 最新提交为 `add9620 feat: add formal skillhub web v4`；clean release PR 仍排除旧 `apps/web`、`apps/web-v2` 和 `apps/web-v3` 实验路径。

2026-05-22 main 合并后回归验证：

- 代码来源：从 `origin/main` 新建 `docs/formal-v4-post-merge-status` 分支，确认基线包含 merge commit `add9620af4d43cd8544dff0fe50f741c9c164f83`。
- 完整验证：`npm run lint`、`npm run build`、`npm run test`、`npm run e2e`、`npm run e2e:visual`、`cd apps/api && uv run pytest`、`git diff --check -- docs README.md apps/web-v4 apps/api scripts .gitignore` 均通过；unit 为 1 个测试文件、10 个测试，API 为 115 passed。
- agent-browser 真实操作：临时启动 `scripts/dev.sh` 到 `18116/13116`，打开 `http://127.0.0.1:13116/skills` 后 snapshot 显示 Web V4 Hub 的 `SkillHub`、`新建 Skill`、筛选和排序控件；点击 `新建 Skill` 后 snapshot 显示新建 Skill 对话框、文件夹上传、zip 上传和禁用的 `创建 Skill` 按钮。

2026-05-22 视觉参考验收记录补充验证：

- 文档更新：新增 `docs/formal-web-v4-visual-reference-acceptance-2026-05-22.md`，把 5 张参考图、当前 visual baseline、验收口径、逐页验收结论、接受偏差和剩余范围固化；README、视觉 smoke 说明、参考图差异清单和本审计已链接该记录。
- 完整验证：`npm run lint`、`npm run build`、`npm run test`、`npm run e2e`、`npm run e2e:visual`、`cd apps/api && uv run pytest`、`git diff --check -- README.md docs apps/web-v4 apps/api scripts .gitignore` 均通过；unit 为 1 个测试文件、10 个测试，API 为 115 passed。
- agent-browser 真实操作：临时启动 `scripts/dev.sh` 到 `18118/13118`，打开 `http://127.0.0.1:13118/skills` 后 snapshot 显示 Web V4 Hub 的 `SkillHub`、`新建 Skill`、筛选和排序控件；点击 `新建 Skill` 后 snapshot 显示新建 Skill 对话框、`约束 tag`、`选择文件夹`、`上传 zip` 和禁用的 `创建 Skill` 按钮。
