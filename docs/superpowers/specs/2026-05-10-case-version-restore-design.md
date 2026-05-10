# Case 历史版本恢复设计

日期：2026-05-10

## 背景

SkillHub 已经支持查看 eval case 的版本历史，但历史只能读，不能从旧版本恢复。对于测试集维护来说，这会让用户在误改 expected output 或 input 后只能手工复制粘贴旧内容，既慢，也容易破坏版本语义。

本轮目标：让用户在 case history 中选择一个旧 `EvalCaseVersion`，恢复为新的当前版本，并生成新的 `EvalSetVersion` 快照。

## 外部实践

- [GitHub Desktop revert](https://docs.github.com/desktop/guides/contributing-to-projects/reverting-a-commit) 明确：revert 会创建一个新 commit，原 commit 保留在历史里。SkillHub 应采用同样原则：恢复旧 case 内容不是覆盖历史，而是创建新 case version。
- [GitLab undo commits](https://docs.gitlab.com/topics/git/undo/) 也建议用 `git revert` 保留历史，因为它比 reset 更安全。SkillHub 的恢复动作也应保留全部旧版本和旧 eval set snapshot。
- [Airtable record revision history](https://support.airtable.com/docs/record-level-revision-history-overview) 把 revision history 放在展开记录的详情里，帮助用户看到谁在什么时候改了什么。SkillHub 已有 inline case history，恢复入口应放在同一个上下文里。
- [Airtable trash restore](https://support.airtable.com/v1/docs/base-trash) 把恢复作为明确动作而非隐式回滚，并受权限控制。SkillHub 当前是单用户 demo，先保留明确按钮，正式权限后再限制角色。

## 语义

恢复旧版本时：

1. 读取目标 `EvalCaseVersion` 的 `input_artifact.content_text` 和 `expected_output_artifact.content_text`。
2. 创建一个新的 `EvalCaseVersion`，版本号递增。
3. 将 `EvalCase.current_version_id` 指向新版本。
4. 创建新的 `EvalSetVersion`，把当前测试集里的该 case membership 替换为新版本。
5. 不删除、不覆盖旧版本。

由于当前模型没有把 case title 放进 `EvalCaseVersion`，恢复只恢复 versioned content：input、expected output、notes。title 仍沿用当前 `EvalCase.title`。

## 用户能看到什么

在 `测评` 页点击某个 case 的 `历史` 后：

- 每个历史版本卡片显示 input、expected output、notes、membership。
- 非当前版本显示 `恢复此版本` 按钮。
- 当前版本显示 `当前版本` 标识，不能恢复自己。
- 点击恢复后：
  - 页面刷新当前 eval set snapshot。
  - 当前 case 仍被选中。
  - case history 展示新增的最新版本。
  - 顶部 notice 显示 `已从 case vN 恢复为新版本。`

## API

新增：

```http
POST /api/eval-cases/{case_id}/restores
```

请求：

```json
{
  "source_case_version_id": "casever_xxx",
  "actor": "product-operator",
  "notes": "Restore from case v1."
}
```

响应沿用 `CreateEvalCaseResult`：

```json
{
  "skill_id": "...",
  "eval_set_id": "...",
  "eval_set_version_id": "...",
  "eval_case_id": "...",
  "eval_case_version_id": "...",
  "input_artifact_id": "...",
  "expected_output_artifact_id": "..."
}
```

## 非目标

- 不恢复 title，因为 title 当前不是 versioned 字段。
- 不恢复 archived case。
- 不做权限系统。
- 不做多 case 批量恢复。

## 验收标准

- 后端测试证明恢复会创建新 case version、移动当前指针、创建新 eval set version，并保留旧 snapshot。
- API 测试证明跨 case 的 source version 不能恢复。
- E2E 覆盖编辑 case 后从历史恢复旧版本，并能在测评页看到旧 expected output 回来。
- 完整 API/Web 验证通过后才提交推送。
