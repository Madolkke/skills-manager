# Web V4 视觉参考验收记录

日期：2026-05-22

结论：`apps/web-v4` 当前 5 个正式页面可以按 Web V4 范围验收。验收口径不是逐像素复刻参考图，而是确认页面结构、操作层级、信息密度、真实数据边界和可重复截图基线已经对齐参考目标；明确排除的能力不在 UI 中伪造入口。

## 输入

| 页面 | 参考图 | 当前截图基线 | 尺寸判断 |
| --- | --- | --- | --- |
| Hub 首页 | `docs/product-ui-reference/01-hub-home.png` | `apps/web-v4/e2e/visual-smoke.spec.ts-snapshots/01-hub-home-chromium-darwin.png` | 参考图与基线均为 `1586x992` |
| Skill 概览 | `docs/product-ui-reference/02-skill-overview.png` | `apps/web-v4/e2e/visual-smoke.spec.ts-snapshots/02-skill-overview-chromium-darwin.png` | 参考图为 `1568x1003`，基线为 `1586x992`，布局比例接近 |
| 测评集管理 | `docs/product-ui-reference/03-eval-set-management.png` | `apps/web-v4/e2e/visual-smoke.spec.ts-snapshots/03-eval-set-management-chromium-darwin.png` | 参考图与基线均为 `1586x992` |
| 手动测评 | `docs/product-ui-reference/04-manual-evaluation.png` | `apps/web-v4/e2e/visual-smoke.spec.ts-snapshots/04-manual-evaluation-chromium-darwin.png` | 参考图与基线均为 `1586x992` |
| 变体管理 | `docs/product-ui-reference/05-variant-management.png` | `apps/web-v4/e2e/visual-smoke.spec.ts-snapshots/05-variant-management-chromium-darwin.png` | 参考图与基线均为 `1586x992` |

## 验收口径

- 参考图是产品方向和页面结构目标，不是像素级设计合同。
- 必须保持白底、扁平、清晰分区、低装饰度的工程产品风格。
- Skill 不显示图标；参考图里的 Skill 图标只作为密度参考。
- 只暴露真实可执行行为；权限、审计、治理、危险区、通知、设置、假全局历史页不纳入 Web V4 主流程。
- `上传版本` 只出现在概览和变体这两个 bundle/version 上下文。
- 每个页面都必须能由 `npm run e2e:visual` 通过固定 seed、固定 viewport 和结构断言重复捕获。

## 逐页验收

### 01 Hub 首页

验收通过。

已对齐：
- 左侧 rail、顶部搜索和筛选、Skill 卡片网格、右侧最近测评区对应参考图主结构。
- Skill 卡片显示维护者、更新时间、score、tags、当前版本、测评集版本和验证状态，不依赖 Skill 图标。
- 最近测评行显示 Skill、得分、当前版本、测评集版本、操作者和时间。
- `查看全部` / `收起` 是右侧列表内的真实展开行为，默认 6 条、展开 7 条，由视觉 smoke 断言。

接受偏差：
- 不提供跨 Skill 全量历史页。当前范围使用首页右栏展开和单个 Skill 内历史证据链，避免把未来信息架构伪装成已完成页面。

### 02 Skill 概览

验收通过。

已对齐：
- 顶部 summary、bundle tree、文件内容区、右侧可靠性卡片对应参考图的信息层级。
- summary 用真实根目录、维护者、状态和默认变体补足视觉重心，不恢复 Skill 图标。
- bundle tree 使用真实 Skill slug 作为根目录，包含子目录、文件叶子、选中态和内容预览。
- 主操作为 `版本管理` / `打开历史`，符合当前真实流程。

接受偏差：
- 不展示无行为图标、假权限、假审计或假治理信息。后续只有在后端和产品字段明确后再扩展身份元数据。

### 03 测评集管理

验收通过。

已对齐：
- 测评集管理与测评执行分离，本页只管理 case 和 case version。
- 左侧包含摘要、搜索、筛选、排序、新增 case 和可扫读 case 列表。
- case 行显示序号、case version、当前/历史状态和生命周期状态。
- 右侧详情区展示 input、expected output、notes 和带连接线的 case version roadmap。

接受偏差：
- 当前数据模型没有 case tags 和多测评集列表，因此不展示参考图里的 case tags 或“返回测评集列表”假导航。

### 04 手动测评

验收通过。

已对齐：
- 页面独立选择 exact `VariantVersion + EvalSetVersion`，并能展开查看真实绑定详情。
- 进度区由确认摘要、结果统计和分布条组成，避免只显示模糊进度。
- case 列表使用状态点、`#position`、case version、结果状态和数字快捷键，适合人工逐条确认。
- 当前 case 详情和底部通过/不通过/下一条/记录动作同属一块操作区域；未确认完前不能记录。

接受偏差：
- 版本详情保持 selector-local panel，不新建独立详情页。独立详情页需要跨页面复用需求和信息架构后再做。

### 05 变体管理

验收通过。

已对齐：
- 变体卡片以 tag 组合表达不同约束，显示当前版本、最新得分、绑定测评集和历史版本数。
- 右侧 inspector 展示当前变体、tags、当前版本摘要、版本线、bundle 摘要和真实动作。
- `上传版本` 是页面内上下文面板，默认带入当前选中变体 tags，可在看着 inspector 的同时追加新版本。
- `Bundle diff` 和 `查看该版本详情` 是 inspector 内真实动作，由视觉 smoke 断言。

接受偏差：
- 当前 diff 是文件级 bundle diff，不伪造逐行代码 diff 工作台。逐行 diff 需要单独设计和测试。

## 当前剩余范围

这些项目不阻塞 Web V4 当前验收，但不应在 UI 中伪造：

1. case tags 和多测评集列表。
2. 跨 Skill 全量测评历史页。
3. 独立 VariantVersion / EvalSetVersion 详情页。
4. 逐行 bundle diff 工作台。
5. 原开发工作树中旧 `apps/web` redesign 脏改动的归档、迁移或丢弃决策。

## 证据链

- 逐图差异与取舍：`docs/formal-web-v4-reference-diff-2026-05-22.md`
- 视觉回归说明：`apps/web-v4/e2e/visual-smoke.md`
- 视觉回归测试：`apps/web-v4/e2e/visual-smoke.spec.ts`
- 发布范围：`docs/formal-web-v4-release-scope-2026-05-22.md`
- 完成度审计：`docs/formal-web-v4-completion-audit-2026-05-21.md`
