# 离线校验与报告

## 运行条件

脚本必须保留在完整仓库中，并使用已经安装后端依赖的 Python。直接使用本地 .venv 可避免包管理器尝试联网；缺依赖时报告环境限制，不自动安装或转为在线校验。

```powershell
apps/backend/.venv/Scripts/python.exe docs/skills/workflow-import-generator/scripts/validate_workflow_import_bundle.py flow.workflow-import.json --mode draft --report-json flow.validation.json
apps/backend/.venv/Scripts/python.exe docs/skills/workflow-import-generator/scripts/validate_workflow_import_bundle.py flow.workflow-import.json --mode strict --expression-contract contract.json --report-json flow.validation.json
```

脚本不加载 .env、不创建数据库连接、不发 HTTP，不执行作者代码。只在内存中规范化与分配验证用身份，输入文件不会重写；仅显式指定的 report-json 路径会写入，不得与 Bundle、契约或脚本重合。报告目录必须已存在。

## 结果与退出码

| 情况 | draft | strict |
| --- | --- | --- |
| 文件/契约/结构错误、非 CLI、禁止字段、后端导入硬限制 | 退出 1 | 退出 1 |
| 硬限制通过，但存在领域 error（如空命令、缺少起点） | 退出 0，status=draft | 退出 1，status=draft |
| 无 error，可有 warning | 退出 0，status=valid | 退出 0，status=valid |

两种模式都运行全部检查。后端导入硬限制包括非法引用、表达式绑定不兼容、函数参数错误、未注册调用和模板错误；不能因为 draft 而忽略。

JSON 包含 mode、passed、status、importChecksPassed、staticValid、contract、hardErrors、diagnostics、expressionDiagnostics、placeholders。importChecksPassed 仅表示以本次离线契约检查通过，不能承诺目标平台必然接受。

- diagnostics 保留后端 Workflow 错误码、severity、selection，增加 location 映射 localId/nodeId/callId/transitionId。
- expressionDiagnostics 保留底层 AST/模板检查的 start/end（UTF-16 偏移）、消息和严重度。部分底层 warning 不进入产品 Workflow 总体面板，因此单独列出，不擅自升为 error。
- hardErrors 中 SKILL_IMPORT_REJECTED 包装后端异常原文；后端异常没有结构化错误码，不伪造其字段或位置。
- SKILL_* 是本脚本的约束码，例如非 CLI、多个起点及具体命令多余输入；与产品诊断区分。
- 后端允许多起点，本 Skill 完整输出要求单一起点。旧定义缺少 angle-v1 仍可校验，新生成文件必须带此标记。

规范化失败时无法进行领域检查，报告只包含已取得的诊断；引用损坏时某些后续表达式无法投影，应先修复硬限制再重跑。校验结果不包含函数体、Bundle 全文或命令回显，但诊断可能引用作者字段文本，仍应妥善保存。

## 本地函数契约

接受用户提供的 `GET /api/workflow-expression-contract` 响应文件形状；此 Skill 不调用该接口。最小自定义声明示例：

```json
{
  "contractVersion": 1,
  "language": "python-eval",
  "functions": {
    "healthy": {
      "parameterSchema": {
        "type": "object", "properties": {"value": {"type": "integer"}},
        "required": ["value"], "additionalProperties": false,
        "x-parameter-order": ["value"]
      },
      "returnSchema": {"type": "boolean"}
    }
  }
}
```

functions 必须为对象。`functions: {}` 表示没有可用函数，不回退内置目录。显式 enabled=false 的记录被排除；内置标记必须合法且名称已知，不能把任意自定义名称标记为内置。自定义参数顺序复用 x-parameter-order，Schema 规则复用后台函数库纯校验器。契约中的 body 字段不读取、不输出、不执行。

未提供文件时使用仓库内置函数静态签名与泛型规则。函数目录可能与目标平台启停状态不同，报告始终标记此限制；本地契约也只是用户提供时刻的快照。只读方法与语言规则来自当前仓库版本。
