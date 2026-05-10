# 快速添加测试用例设计

日期：2026-05-10

## 背景

当前 SkillHub 已经能新增、编辑、归档 eval case，但主要入口仍在右侧 inspector。对真实维护者来说，扩充测评集是高频动作：看到一次 bad case 后，应该能很快把它变成可复用测试用例；整理一批历史 PR 或评审样例时，也不应该逐条打开完整表单。

本轮目标是把 case 进入测评集的路径压短，同时保持 `EvalSetVersion = case version snapshot` 的严谨语义。

## 调研结论

- Linear 的 issue 创建支持快捷键、按钮、预填充 URL 和草稿，说明高频创建动作需要多个入口，但不能牺牲对象模型。参考：<https://linear.app/docs/creating-issues>
- TestRail 对测试用例提供完整表单，也提供 quick outline：用户可先快速添加一个或多个 case 标题，不被完整字段拖慢；但 TestRail 也保留 CSV/XML 导入给批量场景。参考：<https://support.testrail.com/hc/en-us/articles/14438119644692-Adding-test-cases>
- Airtable 支持从表格复制多行再粘贴创建多条 record，适合把已有表格资料批量转成结构化数据。参考：<https://support.airtable.com/docs/adding-duplicating-and-deleting-airtable-records>
- TestRail 创建 test run 时默认包含所有 case，也可按筛选选择，这提示 SkillHub 第一阶段应先让“新增 case 自动进入当前主测评集”保持默认，后续再做选择矩阵。参考：<https://support.testrail.com/hc/en-us/articles/7076838639892>

## 产品设计

在 `测评` 页加入一个主内容区的 `快速添加 case` 面板，位于测评目标和确认进度之间。

它有两个轻量入口：

1. **单条快加**：直接填写标题、input、expected output、notes。提交后留在测评页，新增 case 出现在列表里，并进入手工通过/不通过确认流。
2. **批量粘贴**：从表格或文档粘贴多行，每行格式为 `title | input | expected output | notes`，也支持 tab 分隔。提交前显示可导入条数和跳过条数。

不做“只填标题”的 quick outline。SkillHub 的 case 必须包含 input 和 expected output，否则会削弱测评集质量。这里借鉴 TestRail 的快，但保留 SkillHub 的严谨。

## 数据设计

新增后端命令：

```text
POST /api/eval-cases/batch
```

请求：

```json
{
  "skill_id": "skill_x",
  "actor": "tester",
  "cases": [
    {
      "title": "PR: missing tenant scope",
      "input_text": "Project.all()",
      "expected_output": "Flag missing tenant scope.",
      "notes": "Imported from review backlog."
    }
  ]
}
```

响应：

```json
{
  "skill_id": "skill_x",
  "eval_set_id": "evalset_x",
  "eval_set_version_id": "evalsetver_x",
  "created": [
    {
      "eval_case_id": "case_x",
      "eval_case_version_id": "casever_x"
    }
  ]
}
```

关键约束：

- 一次批量添加只创建一个新的 `EvalSetVersion`。
- 每条 case 仍创建自己的 `EvalCase`、`EvalCaseVersion`、input artifact、expected output artifact。
- 新的 `EvalSetVersion` = 上一个 current eval set version 的 case versions + 本批新增 case versions。
- 空 title、空 input、空 expected output 不入库，API 返回 422 或 400。

## 前端设计

新增 `apps/web/components/eval-cases/quick-add-cases.tsx`：

- 只负责 UI、批量文本解析和本地预览。
- 不直接知道 API 路径，由 `DecisionWorkbench` 注入 `onCreateCases`。
- 批量解析规则：
  - 优先按 tab 拆分。
  - 没有 tab 时按 `|` 拆分。
  - 至少需要三列：title、input、expected output。
  - 第四列作为 notes。
  - 空行忽略。

`DecisionWorkbench` 新增 `createCases`：

- 调 `POST /api/eval-cases/batch`。
- 提交后选中新批次最后一条 case。
- 刷新 skill detail，并把 action mode 切到 `run`。

## 验收标准

1. API 可以一次创建两条 case，并且 skill 只新增一个 eval set version。
2. E2E 可以在测评页批量粘贴两条 case，提交后看到两张 case 卡片。
3. 提交后可以直接把两条 case 标为通过/不通过并记录一次 eval run。
4. 无效批量行不会提交，并在面板里显示跳过数量。
5. 原有 inspector 添加单条 case、编辑 case、归档 case 流程不回归。
6. `uv run pytest`、`npm run typecheck`、`npm run build`、`npm run e2e` 全部通过。

## 非目标

- 不做 CSV 文件上传。
- 不做 case 模板系统。
- 不做 case 分组和多维矩阵。
- 不做从 case history 一键 restore。
- 不改变现有 `POST /api/eval-cases` 单条接口。
