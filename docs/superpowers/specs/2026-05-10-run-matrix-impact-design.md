# Run Matrix Impact 设计

## 背景

History 页已经有 run 列表、run matrix、保存视图和 run-to-run comparison。现在的问题是：用户在矩阵里能看到每个 case 在每次 run 上通过或不通过，但要自己把“对照 run”和“候选 run”的差异在脑中拼起来。实验平台真正有价值的是快速判断收益和风险，所以矩阵需要直接显示 case 级别的修复、回退、稳定和缺失。

## 市场借鉴

- LangSmith comparison view 会基于 source experiment 标出 regressions 和 improvements，并允许用户聚焦这些变化。参考：https://docs.langchain.com/langsmith/compare-experiment-results
- W&B Tables / MLflow compare runs 用表格把多个 run 的参数、指标和样本级结果放在一起，让用户在一个视图中判断版本差异。参考：https://docs.wandb.ai/models/tables/visualize-tables 和 https://learn.microsoft.com/en-us/azure/databricks/mlflow/runs
- Linear display options 把“筛选”和“展示方式”分离，避免每个视图都做成单独页面。参考：https://linear.app/docs/display-options

适配到 SkillHub：当前不新建一个复杂 comparison 页面，而是复用历史页已有的 `对照` / `候选` 选择。用户选中两条 run 后，run matrix 每个 case 行出现 impact chip，明确显示：

- `修复`：对照不通过，候选通过。
- `回退`：对照通过，候选不通过。
- `稳定通过`：两者都通过。
- `仍未通过`：两者都不通过。
- `缺失`：任一 run 没覆盖该 case。

## 用户体验

在 History mode：

1. 用户照常在左侧 run list 点击 `对照` 和 `候选`。
2. Run matrix 表头显示 `Impact` 列，说明当前对比的是所选两条 run。
3. 每个 case 行在 `Impact` 列显示一个色块：
   - 绿色：修复。
   - 红色：回退。
   - 蓝灰：稳定通过。
   - 橙色：仍未通过。
   - 灰色：等待选择或缺失。
4. 如果没有同时选择对照和候选，Impact 列显示 `选择对照/候选`，不阻塞矩阵浏览。

## 技术设计

不改后端。`RunMatrixPanel` 接收 `baselineRunId` 和 `candidateRunId`，用已有 `cells` 计算每个 case 的 impact。计算逻辑放在同文件内的小函数，避免 `DecisionWorkbench` 继续膨胀。

矩阵仍然使用现有 `EvalRunMatrix` 数据结构：

- `runs`：当前筛选下的 run 列。
- `cases`：case 行。
- `cells`：run x case 的结果。

## 测试

- E2E 在现有 run matrix 场景中选择 `0/2` 的对照和 `2/2` 的候选，断言矩阵中出现 `修复` 和 `稳定通过`。
- 视觉基线 `run-comparison-ready` 更新，因为历史页矩阵会新增 Impact 列。
- 完整验证仍为 API pytest、Web typecheck、build、E2E、`git diff --check`。
