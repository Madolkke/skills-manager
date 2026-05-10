# 导入后验证引导设计

日期：2026-05-10

## 背景

当前 SkillHub 已经能上传标准 Skill 文件夹或 zip、添加/编辑/归档测试用例、手工记录通过/不通过测评、查看历史和 promotion review。但新用户导入 skill 后，还需要自己理解下一步应该补 case、跑首轮 eval、再查看证据。这条路径存在于产品能力里，却没有被页面清晰地组织出来。

本轮目标不是新增后端状态，也不是做强制 onboarding，而是把已有能力整理成一个轻量的“验证清单”，让用户导入后立刻知道下一步该点哪里。

## 外部实践

- [Linear Triage](https://linear.app/docs/triage) 把外部进入的 issue 先放入一个特殊 inbox，在进入团队主流程前先 review、update、prioritize。SkillHub 适配为：新导入的 skill 不应直接被当成可靠分发物，而应进入“补测评资产并验证”的维护流。
- [Vercel Deployment Checks](https://vercel.com/docs/deployment-checks) 把 release 前检查作为生产发布前的显式 gate。SkillHub 适配为：`current VariantVersion` 可以存在，但“可信”来自明确的 eval run。
- [Vercel preview promotion](https://vercel.com/docs/deployments/promote-preview-to-production) 的顺序是 find、inspect、test、check errors、promote、verify production。SkillHub 适配为：导入 bundle 后先确认文件，再补 case，再运行 exact eval，再进入 history/promotion。
- [Netlify Deploy Previews](https://docs.netlify.com/deploy/deploy-types/deploy-previews/) 强调先 preview/review/experience changes，再发布生产。SkillHub 适配为：候选或新导入版本应先可体验、可测评，再作为分发依据。

## 用户能看到什么

在 `概览` 页的 default distribution 下方新增一个 `验证清单` 区块：

1. `Bundle 已接入`：显示当前默认 variant 的版本号和文件数。
2. `补齐评测集`：显示当前 eval set 的 case 数；没有 case 时主按钮是 `添加首批 case`。
3. `记录首轮测评`：显示最近 run 的通过率；没有 run 但已有 case 时主按钮是 `打开手工测评`。
4. `证据沉淀`：已有 run 后主按钮变成 `查看证据历史`，引导用户进入 run history 和 accepted verification。

区块不是弹窗，不遮挡工作台，不阻止用户自由切 tab。它只把下一步动作放到用户刚完成导入后最容易看到的位置。

## 状态来源

清单只从现有 read model 推导，不创建新表：

- `bundleReady = Boolean(defaultVariant.current_version)`
- `caseCount = evalSetDetail.cases.length`
- `runReady = Boolean(latestRun)`
- `score = passRate(latestRun)`

这样不会出现“清单状态”和真实数据不一致的问题。

## 交互规则

- 点击 `添加首批 case`：右侧 inspector 切到 `新增 case`。
- 单条 case 提交成功后：自动切到 `测评` tab，并把 inspector 切到 `记录测评`，让用户立即确认通过/不通过。
- 点击 `打开手工测评`：切到 `测评` tab，并聚焦记录测评语义。
- 点击 `批量粘贴 case`：切到 `测评` tab，用户使用已有 `QuickAddCases` 的批量模式。
- 点击 `查看证据历史`：切到 `历史` tab。

## 非目标

- 不新增 onboarding modal。
- 不新增后端 workflow 状态。
- 不强制用户完成清单。
- 不自动生成测试用例。
- 不改 promotion review 后端契约。

## 验收标准

- 导入标准 skill bundle 后，`概览` 页显示 `验证清单`。
- 导入后没有 case 时，清单主动作是 `添加首批 case`。
- 添加第一条 case 后，页面自动进入 `测评` tab，用户能直接看到 case 并标记通过/不通过。
- 记录首轮 run 后，回到 `概览` 页能看到清单显示首轮测评完成，并提供 `查看证据历史`。
- Playwright E2E 覆盖导入后引导全路径。
- 不破坏现有 22 条 E2E 主路径。

## 自检

- 没有 `TBD` 或悬空字段。
- 所有状态都由已有 `SkillDetail`、`EvalSetVersionDetail`、`EvalRunRecord` 推导。
- 设计只覆盖一个前端引导任务，适合单独实现和提交。
