# 主工作区 Skill Launchpad 设计

日期：2026-05-13

## 背景

SkillHub 已经把 case 编辑、variant 创建、候选版本追加迁入主工作区，但 first-run 的 `导入 bundle` 和 `新建 skill` 仍主要依赖右侧 inspector。对新用户来说，第一个成功动作应该发生在中间主工作区，而不是让用户先理解侧栏。

## 外部实践

- Vercel 的新项目页把 `Import Git Repository` 放在主流程中，并把选择来源、配置项目、生成部署串成单条路径。适配到 SkillHub：标准 Skill bundle 导入应成为 first-run 主操作，导入后进入验证清单。来源：<https://vercel.com/docs/getting-started-with-vercel/import>
- GitHub 新建仓库页面把 owner、repository name、visibility、初始化选项集中在一个主表单。适配到 SkillHub：空白 skill 创建应在主区完成，字段保持少而明确。来源：<https://docs.github.com/en/repositories/creating-and-managing-repositories/creating-a-new-repository>
- Linear 把创建 issue 设计为最高频动作，支持快捷键、按钮和模板入口。适配到 SkillHub：主区 launchpad、命令菜单、inspector 都保留同一能力，但 first-run 应优先走主区。来源：<https://linear.app/docs/creating-issues>
- Raycast 创建扩展时先选模板，再按屏幕提示运行开发命令。适配到 SkillHub：launchpad 不只收集字段，还要提示“导入后补 case、记录 run”的下一步。来源：<https://developers.raycast.com/basics/create-your-first-extension>

## 设计目标

1. 空工作台的 overview 直接展示 `SkillLaunchpad`，包含 `导入标准 Skill` 和 `新建空白 Skill` 两个模式。
2. 导入模式支持 owner、tags、variant label、文件夹、zip、前端预览和 bad preview 禁用提交。
3. 创建模式支持 slug、owner、baseline variant、tags、summary、change summary。
4. 提交后复用现有 `importSkill` / `createSkill` 数据流，导入成功仍进入概览验证清单。
5. 右侧 inspector 和命令菜单保留原能力，避免破坏熟手路径。

## 非目标

- 不新增后端接口。
- 不重做整个 catalog 首页。
- 不做多步骤 wizard；当前保持单屏两模式，避免引入保存草稿和跨步骤校验状态。
- 不把 skill 设置迁入主区；本任务只处理 first-run 创建/导入。

## 交互细节

- launchpad 使用 segmented control 切换 `导入 bundle` / `新建 skill`。
- 导入模式默认出现，因为标准 Skill bundle 是产品最核心路径。
- 文件夹和 zip 仍互斥，沿用现有 preview 逻辑；缺少 `SKILL.md` 时显示阻塞预览并禁用提交。
- 创建模式强调“草稿 skill”，避免用户误以为没有 bundle 也已可分发。
- launchpad 右侧放一个短 checklist：`导入 bundle -> 补 case -> 记录首轮 run -> 接受验证依据`。

## 测试策略

- 新增 E2E：空工作台直接通过 `.skillLaunchpad` 导入标准 folder bundle，断言进入新 skill 概览和导入成功提示。
- 新增 E2E：空工作台通过 `.skillLaunchpad` 新建空白 skill，断言进入新 skill 概览并展示 default variant。
- 更新现有视觉基线：空工作台 launchpad，保证 first-run UI 不退回到只有两个小按钮。
- 完整回归继续跑 API pytest、web typecheck、web build、Playwright E2E 和 `git diff --check`。
