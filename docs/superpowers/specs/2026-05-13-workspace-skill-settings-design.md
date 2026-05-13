# 主工作区 Skill 设置设计

日期：2026-05-13

## 背景

前几轮已经把 first-run launchpad、variant 创建、候选版本追加和 case 编辑迁入主工作区。剩下一个明显断点：用户创建或导入 skill 以后，修改 skill 身份、归属和默认分发仍主要依赖右侧 inspector。对成熟产品来说，当前对象的基础属性应该在对象上下文里可见、可编辑，而不是藏在工具抽屉里。

## 外部实践

- Vercel 的项目 General Settings 明确把项目名、构建设置、项目 ID 等基础配置放在项目设置页，并对项目名给出字符约束。适配到 SkillHub：skill slug/owner/default variant 需要成为可保存的结构化设置，而不是自由散落的表单字段。来源：<https://vercel.com/docs/project-configuration/general-settings>
- Linear 的 Project overview 允许用户在 overview 里查看和编辑项目摘要、属性、名称和描述，也可以从详情侧栏编辑同一批属性。适配到 SkillHub：主区设置和 inspector 应该是同一能力的两个入口，主区负责高频、可解释的上下文编辑。来源：<https://linear.app/docs/project-overview>
- GitHub 仓库 topics 出现在仓库首页，管理员可以从仓库主页的 About 区域编辑 metadata；topics 不是分支，也不是历史血缘，而是用于发现和分类的属性。适配到 SkillHub：默认 variant 和 tags 代表当前分发/约束语义，应在 skill 主页附近可见。来源：<https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/classifying-your-repository-with-topics>
- Notion 支持从数据库设置管理属性，也支持直接点击单个属性编辑值。适配到 SkillHub：保留 inspector 的完整表单，同时把当前 skill 的关键属性做成主区可编辑面板。来源：<https://www.notion.com/help/database-properties>

## 设计目标

1. 在 skill 概览主工作区新增 `SkillSettingsPanel`，用于编辑当前 skill 的 `slug`、`owner_ref` 和默认 `variant`。
2. `PATCH /api/skills/{skill_id}` 支持可选 `default_variant_id`，并强制该 variant 属于同一个 skill。
3. 主区设置保存后刷新 catalog、header、概览 hero 和 verification binding。
4. 右侧 inspector 的 `Skill 设置` 继续可用，并复用同一个后端契约。
5. 归档仍保留在 inspector；本轮不把危险操作前置到主区，避免成熟产品第一屏过早出现 destructive action。

## 非目标

- 不做权限模型。
- 不做完整 settings 路由或多页设置中心。
- 不编辑 variant 的 label/summary/tags；这些仍通过 variant 相关流程维护。
- 不做 default variant 切换的 promotion gate；本轮只是补齐已有 `default_variant_id` 的显式管理入口。

## 交互细节

- `SkillSettingsPanel` 放在概览页 metrics 下方、bundle 区域上方。
- 面板左侧是 `Identity`：显示并编辑 slug、owner。
- 面板右侧是 `Default distribution`：select 展示所有 active variants，选项包含 label 和 tags；保存后 `skill.default_variant_id` 指向选择的 variant。
- 面板底部展示当前默认 variant 的 current version、tags 和最近 accepted verification 摘要，避免用户只看到一个孤立 select。
- 保存按钮禁用于 busy 状态；错误继续走现有 notice。

## 测试策略

- API：新增测试 `PATCH /api/skills/{skill_id}` 可以更新 slug、owner 和 `default_variant_id`，并刷新 detail summary。
- API：新增测试跨 skill variant 不能被设为 default。
- E2E：导入 skill 后创建第二个 variant，在概览主区把 default distribution 切到第二个 variant，断言 hero、catalog tags 和默认 variant 内容刷新。
- 视觉：更新 imported overview 视觉基线，覆盖主区设置面板。
- 完整回归继续跑 API pytest、web typecheck、web build、Playwright E2E 和 `git diff --check`。
