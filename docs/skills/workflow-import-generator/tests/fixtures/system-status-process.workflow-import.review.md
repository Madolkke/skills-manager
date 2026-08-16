# 工作流导入审阅报告

## 来源

- 源文档：`system-status-process.md`
- 已映射步骤：检查系统状态、需要人工查看结果
- 已映射 Collection：`inspect-system-status`

## 待补全

| Collection | 原因 | 需要补全 |
| --- | --- | --- |
| `inspect-system-status` | 流程说明未提供设备命令、输出字段或 Schema。 | 单行 CLI 命令、输出字段和 JSON Schema。 |

## 条件

文档没有提供可类型化的状态字段，已保留“采集完成后人工查看结果”为 `conditionText`，未生成 `conditionExpression`。

## 本地校验

```powershell
uv run --project apps/backend python docs/skills/workflow-import-generator/scripts/validate_workflow_import_bundle.py docs/skills/workflow-import-generator/tests/fixtures/system-status-process.workflow-import.json
```

预期：结构和引用校验通过，并报告一个 CLI 执行占位项。
