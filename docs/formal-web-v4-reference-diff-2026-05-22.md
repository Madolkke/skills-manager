# Web V4 正式版参考图差异清单

日期：2026-05-22

目的：把 `docs/product-ui-reference/` 里的 5 张目标参考图和当前 Web V4 visual baseline 的差异固化成可执行验收清单。这个文件不是完成证明，而是后续 UI 收敛的工作单。

## 输入

| 页面 | 目标参考图 | 当前基线 |
| --- | --- | --- |
| Hub 首页 | `docs/product-ui-reference/01-hub-home.png` | `apps/web-v4/e2e/visual-smoke.spec.ts-snapshots/01-hub-home-chromium-darwin.png` |
| Skill 概览 | `docs/product-ui-reference/02-skill-overview.png` | `apps/web-v4/e2e/visual-smoke.spec.ts-snapshots/02-skill-overview-chromium-darwin.png` |
| 测评集管理 | `docs/product-ui-reference/03-eval-set-management.png` | `apps/web-v4/e2e/visual-smoke.spec.ts-snapshots/03-eval-set-management-chromium-darwin.png` |
| 手动测评 | `docs/product-ui-reference/04-manual-evaluation.png` | `apps/web-v4/e2e/visual-smoke.spec.ts-snapshots/04-manual-evaluation-chromium-darwin.png` |
| 变体管理 | `docs/product-ui-reference/05-variant-management.png` | `apps/web-v4/e2e/visual-smoke.spec.ts-snapshots/05-variant-management-chromium-darwin.png` |

## 统一取舍

- 保持白底、扁平、低阴影的工程产品风格；不回到深色旧工作台。
- Skill 不显示图标。这是产品目标明确要求，参考图里的 Skill 图标只作为布局密度参考，不作为实现目标。
- 不暴露未成熟的权限、审计、治理、危险区、通知、设置和用户菜单。全局 rail 和顶部 actor 只保留真实可用入口。
- `上传版本` 只属于概览和变体这两个 bundle/version 上下文；测评集、测评、历史页不显示这个动作。
- 视觉基线用于防退化，不代表已经逐像素达到参考图。

## 逐图差异

### 01 Hub 首页

已对齐：
- 左侧 rail、顶部大标题、搜索框、筛选 tabs、卡片网格和右侧最近测评区的主布局已经接近参考图。
- Skill 卡片不显示 Skill 图标，符合最终产品要求。
- 卡片底部有验证得分、测评集版本、当前版本三个核心指标。
- 卡片上半区已补充维护者、更新时间和得分胶囊，在不恢复 Skill 图标的前提下补足参考图里的信息密度。
- 右侧最近测评区已强化层级，每条记录显示 Skill、得分、当前版本、测评集版本、操作者和时间。
- 最近测评入口已从 `查看已验证` 筛选命令改为真实的 `查看全部` / `收起` 列表操作；默认显示 6 条，超过 6 条时在同一真实列表内展开全部记录，不伪造全局历史页。

主要差距：
- 暂无阻塞差距；跨 Skill 全量测评历史页不属于当前 5 张参考图的收敛范围，也不是核心闭环必需项。当前版本保留首页右栏本地展开和单个 Skill 内的历史证据链，不在 Hub 里伪造全局历史页。

建议任务：
- Future：如果后续产品明确需要跨 Skill 全量测评历史页，需要先定义独立信息架构，再决定是否把右栏 `查看全部` 升级为真实导航；当前正式版不纳入。

### 02 Skill 概览

已对齐：
- 顶部 summary、bundle 文件树、代码内容区、右侧可靠性卡片的布局已经和参考图一致。
- bundle 树使用真实 Skill slug 作为根目录，并能查看具体文件内容。
- bundle tree 已从平铺分组收敛为根目录、子目录和文件叶子的可展开树，文件夹和文件有一致图标、缩进和选中态。
- 主操作已经改为 `版本管理` / `打开历史`，避免把未成熟能力包装成错误承诺。
- 当前版本指标已经使用 `VariantVersion.created_at` 显示更新时间；视觉 smoke 为稳定截图会 mask 动态日期，但运行时信息可见。
- Summary 左侧已用真实根目录、维护者和状态组成的身份信息 tile 补足视觉重心，不恢复参考图里的 Skill 图标；默认变体值已改为胶囊表达，避免 tag 组合像版本号一样占用大号数字层级。

主要差距：
- 暂无阻塞差距；当前版本刻意不恢复 Skill 图标，后续只在真实元数据需要强化时继续微调。

建议任务：
- P3：如果后续需要展示更多真实 Skill 身份元数据，可以扩展 summary 身份 tile；不要加入无行为图标或假治理信息。

### 03 测评集管理

已对齐：
- 测评集管理和测评执行已经拆开，页面只管理 case 与 case version。
- 左侧有测评集摘要、搜索、筛选、排序、新增 case 和 case 列表。
- 右侧详情区有 input、expected output、notes 和版本历史。
- 版本历史已改为带 marker 和连接线的横向 version roadmap，保留下一版待创建状态。
- 已移除无 handler 的更多按钮。
- case 列表已用真实 position、case version、当前/历史状态和 lifecycle status 增强扫读密度，在后端不支持 case tags 前不伪造标签。

主要差距：
- 参考图的 case 列表展示 case tags；当前数据模型不支持 case tags，本版用真实 case metadata 替代，不把伪标签写进 UI。
- 参考图左上有“返回测评集列表”，当前 Web V4 只有一个 primary eval set，暂不需要假导航。

建议任务：
- P2：只有在后端支持 case tags 或多测评集列表后，再补 tags 与“返回测评集列表”导航。

### 04 手动测评

已对齐：
- 独立测评页、exact VariantVersion + EvalSetVersion 选择、进度汇总、case 列表、case 详情和底部操作条都已形成闭环。
- 底部操作条已经对齐当前 case 详情区，不再横跨左侧 case 列表。
- 未全部确认前不能记录；通过/不通过/下一条/记录动作清晰。
- case 列表已压缩为状态点、`#position`、标题、case version、结果状态和数字快捷键的紧凑行，并修复后端 0-based position 导致第二条显示为 1 的问题。
- 进度区已收敛为“摘要卡 + 结果统计 + 结果分布条”的三段式布局，环形进度、已确认数量、总 case 数和分布条比例更接近参考图。
- selector 旁已补 `查看详情`，点击后展示 VariantVersion / EvalSetVersion 的真实绑定详情，包括变体、版本、创建者、内容 digest、bundle 文件数、测评集和 case 数。

主要差距：
- 暂无阻塞差距；如果后续要做更深的版本详情页，需要先定义 VariantVersion / EvalSetVersion 信息架构，而不是把当前测评页做成假导航。

建议任务：
- P3：只有在需要跨页面复用版本详情时，再把当前 selector-local detail panel 升级为独立详情页。

### 05 变体管理

已对齐：
- 变体由 tag 组合定义，卡片展示当前版本、最新得分、绑定测评集和版本历史。
- 右侧 inspector 展示当前变体、tags、最新得分、测评集、版本历史和 bundle 内容。
- 右侧 inspector 的版本历史已改为水平 version line，并保留当前版本摘要，和参考图的线性版本表达一致。
- `上传版本` 位于变体上下文，动作边界正确。
- 变体页的 `上传版本` 已从居中 modal 收敛为页面内侧卡，默认带入当前选中变体的 tags，用户可以边看变体卡片和右侧 inspector 边上传 bundle。
- inspector 底部已补 `Bundle diff` 和 `查看该版本详情` 两个真实动作；`Bundle diff` 比较当前版本和上一版本的 bundle 文件，版本详情展示当前 VariantVersion 的创建信息、内容 digest 和文件数。

主要差距：
- 暂无阻塞差距；当前是 inspector 内联详情，不伪造独立 diff 工作台或详情页。

建议任务：
- P3：只有在需要跨版本逐行代码 diff 时，再升级到独立 diff 工作台；当前先保留轻量 bundle 文件级 diff。

## 优先级

1. **测评集 tags / 多测评集列表。** 只有在后端支持 case tags 或多测评集列表后，再补参考图里的 tags 与“返回测评集列表”导航。
2. **Skill 概览身份元数据扩展。** 当前 summary 视觉重心已对齐；只有出现真实身份字段需求时再继续扩展。
3. **手动测评深层版本详情页。** 当前 selector-local detail panel 已覆盖测评前核对；只有出现跨页面复用需求时再升级。
4. **变体深层 diff 工作台。** 当前 inspector 内联 `Bundle diff` 已覆盖文件级核对；只有需要逐行代码 diff 时再升级。
5. **跨 Skill 全量测评历史页。** 当前正式版不纳入；如果后续产品范围明确需要，再另起信息架构任务。

## 每轮验收要求

后续关闭任何一项差异时，至少需要：

- 更新对应页面实现和 visual baseline。
- 更新本文件，把差异从“主要差距”移到“已对齐”或注明放弃原因。
- 运行 `npm run lint`、`npm run build`、`npm run test`、`npm run e2e`、`npm run e2e:visual`。
- 运行 `cd apps/api && uv run pytest`。
- 使用 `agent-browser` 做真实操作验证，不能只依赖截图。
