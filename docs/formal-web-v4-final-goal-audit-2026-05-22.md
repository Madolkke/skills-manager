# SkillHub Web V4 最终目标验收审计

日期：2026-05-22

结论：**正式版目标可以验收。** 当前权威版本是 `origin/main` 的 `a45d4142b1b06fdf1d663e3ab03f1715744337da`。该版本已经把 Web V4 正式代码、API、默认启动脚本、中文 README、参考图差异记录、视觉参考验收记录和发布范围说明合并到 GitHub `main`。

## 权威范围

- 正式代码：`apps/api`、`apps/web-v4`、`scripts/dev.sh`、`scripts/dev-v4.sh`。
- 视觉目标：`docs/product-ui-reference/01-hub-home.png` 到 `05-variant-management.png`。
- 视觉基线：`apps/web-v4/e2e/visual-smoke.spec.ts-snapshots/` 下 5 张截图。
- 正式文档：`README.md`、`docs/formal-web-v4-reference-diff-2026-05-22.md`、`docs/formal-web-v4-visual-reference-acceptance-2026-05-22.md`、`docs/formal-web-v4-release-scope-2026-05-22.md`。
- 排除范围：旧 `apps/web`、`apps/web-v2`、`apps/web-v3` 历史工作台不属于正式版完成证据；原开发工作树里旧 `apps/web` 的本地脏改动已记录在 `docs/legacy-web-worktree-audit-2026-05-22.md`，不混入正式版发布。

## 逐项验收

| 目标要求 | 权威证据 | 结论 |
| --- | --- | --- |
| 5 张参考图对应 Hub 首页、Skill 概览、测评集管理、手动测评、变体管理 | `docs/product-ui-reference/` 5 张图存在；`npm run e2e:visual` 捕获 5 个对应页面；视觉参考验收记录逐页说明已对齐点和接受偏差。 | 已验收 |
| 白底扁平风格，统一不一致参考图 | `apps/web-v4` 采用独立白底 Web V4 外壳；视觉参考验收记录把参考图统一为白底、扁平、低装饰度工程产品风格。 | 已验收 |
| Skill 不需要图标 | Hub 卡片和 Skill 概览不依赖 Skill 图标；视觉参考验收记录明确图标只是密度参考。 | 已验收 |
| 新建 Skill，上传标准文件夹或 zip | `NewSkillModal`、`BundlePicker`、`sourceFromFiles` 支持 folder/zip；API 测试覆盖 folder import、zip import、frontmatter 错误和 zip 错误；README 记录使用方式。 | 已验收 |
| 通过 tags 创建或更新变体 | `VariantUploadForm` 按 tags 匹配已有变体或创建新变体；E2E 用同一组 tags 追加 `VariantVersion`。 | 已验收 |
| 查看 bundle 文件内容 | `OverviewPage` 使用 `BundleBrowser` 展示可展开根目录、子目录、文件叶子和文件内容；E2E/visual smoke 断言 `SKILL.md`、`checklist.md`、`examples/`、`pr.diff` 可见。 | 已验收 |
| 管理测评集和测试用例版本 | `EvalSetsPage` 新增 case、编辑为新版本；`CaseVersionRoadmap` 展示 v1、当前 v2 和待创建下一版；后端测试验证 EvalSetVersion 快照不回写历史。 | 已验收 |
| 独立测评页选择 exact `VariantVersion + EvalSetVersion` | `EvaluatePage` 使用两个 version selector；`recordEvalRun` 发送 exact IDs；视觉 smoke 断言两个版本详情入口和真实绑定详情。 | 已验收 |
| 逐 case 手动标记通过/不通过并记录结果 | 正式 E2E 完成 pass 标记和 `记录本次测评`；API/SQL 测试验证结果 key 必须属于当前 EvalSetVersion 且覆盖所有 case。 | 已验收 |
| 查看历史版本和证据链 | `HistoryPage` 展示 `VariantVersion`、`EvalSetVersion`、case result、case version、input/expected digest；E2E 断言证据链可见。 | 已验收 |
| 不暴露权限、审计、治理、危险区等未成熟功能 | `rg` 在 `apps/web-v4/src` 未发现主流程暴露权限、治理、危险区 UI；命中的 `danger` 仅是 toast 语义，`audit_events` 仅是 API 类型字段。 | 已验收 |
| 测评集管理和测评执行分离 | `EvalSetsPage` 只管理 case；`EvaluatePage` 只执行手动测评；E2E 断言测评集、测评、历史页不显示不相关的 `上传版本` 主操作。 | 已验收 |
| 不用跳到页面下方冒充导航 | Skill 详情使用 tab 和 URL query 导航；E2E 通过 tab 切换正式流程。 | 已验收 |
| 组件和样式避免 demo 债务 | Web V4 从旧 `apps/web` 分离；主要 TSX/CSS 文件都低于 300 行，最大 TSX 文件 `EvaluatePage.tsx` 为 284 行；共享组件包括 `BundleBrowser`、`VariantInspector`、`ManualProgressPanel`、`CaseVersionRoadmap`。 | 已验收 |
| 产品文档、README 和用户可见说明默认中文 | README、验收记录、差异清单、发布范围和审计记录均为中文；代码标识和第三方产品名保留英文。 | 已验收 |
| 一键启动和核心流程说明 | README 记录 `bash scripts/dev.sh`、health check、建议试用路径、核心流程跑通清单和验证命令；默认脚本启动 `apps/web-v4`。 | 已验收 |
| 阶段性稳定后上传 GitHub | PR #1、#2、#3 均已合并到 `main`；`origin/main` 最新为 `a45d4142 docs: add visual reference acceptance audit`；开放 PR 为空。 | 已验收 |

## 最终验证

在干净 worktree `/Users/xx/.config/superpowers/worktrees/skills-manager/final-formal-v4-audit`，基于 `origin/main` 的 `a45d4142b1b06fdf1d663e3ab03f1715744337da` 执行：

```bash
cd apps/web-v4 && npm ci
cd apps/web-v4 && npm run lint
cd apps/web-v4 && npm run build
cd apps/web-v4 && npm run test
cd apps/web-v4 && npm run e2e
cd apps/web-v4 && npm run e2e:visual
cd apps/api && uv run pytest
git diff --check -- README.md docs apps/web-v4 apps/api scripts .gitignore
```

结果：

- `npm ci`：211 个 package 安装完成，0 vulnerabilities。
- Web lint：通过。
- Web build/typecheck：通过。
- Web unit：1 个测试文件、10 个测试通过。
- Web E2E：1 条正式主流程通过。
- Web 视觉 smoke：1 条测试捕获 5 个正式参考页面，通过。
- API pytest：115 passed。
- `git diff --check`：通过。

真实浏览器验证：

- 临时启动 `scripts/dev.sh` 到 `18119/13119`。
- `agent-browser` 打开 `http://127.0.0.1:13119/skills`，snapshot 显示 Web V4 Hub 的 `SkillHub`、`新建 Skill`、搜索、筛选、排序、卡片/列表视图和最近测评区。
- 点击 `新建 Skill` 后，snapshot 显示新建 Skill 对话框、`约束 tag`、`选择文件夹`、`上传 zip`、`取消` 和禁用的 `创建 Skill` 按钮。

GitHub 验证：

- `gh pr list --state open` 返回空数组。
- `origin/main` 最新提交为 `a45d4142 docs: add visual reference acceptance audit`。
- PR #3 合并前 GitHub Actions 中 `Backend tests`、`Formal API domain tests`、`Demo frontend build`、`Formal web build` 全部 `SUCCESS`。

## 后续非阻塞范围

以下不是当前正式版目标的阻塞项，后续应独立立项：

1. 旧 `apps/web` 本地 redesign 脏改动的归档、迁移或丢弃。
2. case tags 和多测评集列表。
3. 跨 Skill 全量测评历史页。
4. 独立 VariantVersion / EvalSetVersion 详情页。
5. 逐行 bundle diff 工作台。
