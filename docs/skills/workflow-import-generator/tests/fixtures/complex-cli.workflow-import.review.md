# 网络巡检离线生成审阅

- 来源：complex-cli.md；示例维护日期：2026-09-20。
- 两个步骤、一个结论、四个 CLI 定义、五个调用。routes 定义在两步骤复用；fabric 采集三次。
- 已确认：实际命令、输入类型、设备角色、全部输出 Schema、分支条件及去向均取自源说明，没有使用数据库或在线目录。
- 没有命令占位。步骤二 healthy=false 的处置在源文档中未定义，保留作者原意供人工补齐；静态通过不证明业务分支完备。
- 首步骤 parallelBranches=true，第二步骤 false；当前外部执行器投影仍忽略该字段。
- 函数契约：repository-builtins；目标环境可能不同。只有 len 被使用，不执行任何函数体。
- 所有定义均有调用；来源是合成验收契约，不含生产回显或凭据。Schema 由源说明明确给出，不从样例推断。

## 静态校验

```powershell
apps/backend/.venv/Scripts/python.exe docs/skills/workflow-import-generator/scripts/validate_workflow_import_bundle.py docs/skills/workflow-import-generator/tests/fixtures/complex-cli.workflow-import.json --mode strict
```

结果：strict 退出 0，status=valid，无导入硬限制、领域错误或表达式诊断。未执行命令、回显解析、同步或导入，不代表运行能力验收。
