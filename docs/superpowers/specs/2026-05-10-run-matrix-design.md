# Run Matrix 设计规格

日期：2026-05-10

## 背景和调研结论

SkillHub 现在已经能记录多次 `EvalRun`，也能比较两次 run。但固定的两两比较不能覆盖用户之前提到的“多维表格，用户想怎么查询就怎么查询”。本轮先做 read-only `Run matrix`，把现有历史页升级成更像实验分析工作台的入口。

参考模式：

- Linear filters：几乎所有列表都可以临时筛选，筛选后可进一步保存成自定义 View。SkillHub 本轮先复用历史页已有筛选，不做保存视图。来源：https://linear.app/docs/filters/
- Airtable views：同一份底层记录可以有不同 view，并支持隐藏、筛选、排序、分组。SkillHub 本轮采用“同一 run 数据，增加矩阵视角”，而不是新建另一套数据。来源：https://support.airtable.com/docs/en/getting-started-with-airtable-views
- LangSmith experiment comparison：比较多个 experiments 时支持过滤、列显示、compact/full/diff，以及 regression/improvement。SkillHub 本轮先把多 run × 多 case 的 pass/fail 关系铺开，后续再加入 regression coloring 和 saved view。来源：https://docs.langchain.com/langsmith/compare-experiment-results
- W&B Tables：用表格比较模型版本、训练时间和具体样本，支持 filter/group/sort/save view。SkillHub 本轮借鉴“行是样本/case，列是运行/run”的心智模型。来源：https://docs.wandb.ai/models/tables/visualize-tables

## 用户能看到什么

在 `历史` 页，run 列表上方或下方出现一个 `Run matrix` 区块：

- 顶部摘要：`N runs · M cases · 当前筛选生效`。
- 列：当前历史筛选下最近的 eval runs，列头展示 variant label、variant version、eval set version、通过率。
- 行：这些 runs 覆盖到的 eval case，展示 case 标题。
- 单元格：
  - `通过`：绿色低噪声 badge。
  - `不通过`：红色低噪声 badge。
  - `未覆盖`：灰色 dash，表示这个 run 的 eval set snapshot 没有该 case version。
- 点击 run 行仍然使用原来的详情面板；矩阵只读，不改变用户当前记录结果的流程。

## 后端契约

新增：

```text
GET /api/skills/{skill_id}/eval-run-matrix
```

Query 参数复用 history：

- `variant_version_id`
- `eval_set_version_id`
- `strategy`
- `status`
- `limit`

返回结构：

```json
{
  "skill": { "...": "..." },
  "runs": [
    {
      "eval_run": { "...": "..." },
      "variant": { "...": "...", "tags": ["codex"] },
      "variant_version": { "...": "..." },
      "eval_set": { "...": "..." },
      "eval_set_version": { "...": "..." }
    }
  ],
  "cases": [
    {
      "case": { "id": "case_1", "title": "PR: missing tenant scope" },
      "versions": [
        { "case_version_id": "casever_1", "version_number": 1 }
      ]
    }
  ],
  "cells": [
    {
      "run_id": "evalrun_1",
      "case_id": "case_1",
      "case_version_id": "casever_1",
      "passed": true,
      "score": 1
    }
  ]
}
```

矩阵按 `case_id` 合并不同 case version；cell 保留 exact `case_version_id`，避免掩盖 snapshot 语义。

## 前端设计

- 在 `DecisionWorkbench` 新增 `runMatrix`、`runMatrixLoading` state。
- `loadRunMatrix(skillId, filters)` 与 `loadRunHistory` 使用同一组 filters。
- 新增 `components/run-matrix/run-matrix-panel.tsx`，避免继续膨胀 `decision-workbench.tsx`。
- `HistoryPane` 接收 matrix props，在 history grid 里渲染矩阵。
- CSS 使用横向滚动容器，列宽固定，避免 run 数变多时挤坏三栏布局。

## 测试策略

- Repository 测试：同一个 skill 下两条 case、两次 run，断言矩阵行、列、cell 状态正确。
- API 测试：验证 endpoint 返回矩阵，并尊重 `variant_version_id` 过滤。
- E2E 测试：导入 skill，批量添加两条 case，记录一次一过一不过；追加 candidate 后记录一次全过；打开历史，断言矩阵有两个 run 列、两个 case 行，并显示 `通过`/`不通过`。

## 非目标

- 不做 saved view 持久化。
- 不做矩阵内编辑 pass/fail。
- 不做跨 skill 聚合。
- 不做无限滚动和列虚拟化；本轮 `limit` 仍最多 200。
