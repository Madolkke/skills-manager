# Workflow 文档 Schema

本文档描述 SkillHub 当前 Workflow 文档格式 **schema v3**。它是 `WorkflowBundle` 的持久化结构，字段名使用 API 中的 camelCase 形式。

权威实现：

- 后端结构定义：`apps/backend/skillhub/models/rules/workflows/schema.py`
- 前端镜像类型：`apps/frontend/src/types/workflow.ts`
- 领域校验：`apps/backend/skillhub/models/rules/workflows/validation.py`

## 基本规则

- `document_schema_version` 存在数据库 `workflows` 表中，不写入 Bundle 内部；当前值为 `3`。
- 当前只接受 schema v3，不兼容 v2 的步骤输入、`step_input` Binding 或 Collection 输出展示名称。
- 所有对象禁止未知字段，字段名使用严格类型校验。
- Python 字段名通过 alias 转换为 camelCase，例如 `step_type` 对应 `stepType`，`data_type` 对应 `dataType`。
- `id` 用于身份和结构引用，创建后不应修改或复用。
- `key` 用于参数、设备角色、Collection 或输出字段的可读引用；节点和 Transition 不再有 `key`。
- `name` 用于展示，不承担结构引用职责。

## 顶层结构

```json
{
  "documentType": "workflow_bundle",
  "workflow": {
    "id": "workflow-001",
    "revision": 1,
    "metadata": {},
    "inputs": [],
    "deviceRoles": [],
    "nodes": []
  },
  "collectionSnapshots": []
}
```

### WorkflowBundle

| 字段 | 类型 | 必填 | 含义 |
| --- | --- | --- | --- |
| `documentType` | `"workflow_bundle"` | 是 | 文档类型常量，用于识别 Workflow Bundle。 |
| `workflow` | `Workflow` | 是 | Workflow 主体定义。 |
| `collectionSnapshots` | `CollectionDefinition[]` | 否，默认 `[]` | 当前 Workflow 直接引用的 Collection 精确版本快照。 |

`collectionSnapshots` 不是全局 Collection Catalog。每个 `CollectionCall.definition` 必须能在这里找到对应的 `id + revision`。

## Workflow

| 字段 | 类型 | 必填 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| `id` | `string` | 是 | - | Workflow 身份。通常与 `workflows.id` 对应。 |
| `revision` | `integer` | 是 | - | Workflow 文档修订号。保存成功后由服务端管理。 |
| `metadata` | `WorkflowMetadata` | 是 | - | Workflow 的作者可编辑元信息。 |
| `inputs` | `Parameter[]` | 否 | `[]` | Workflow 级别的输入参数声明。 |
| `deviceRoles` | `DeviceRole[]` | 否 | `[]` | Workflow 使用的逻辑设备角色。 |
| `nodes` | `(ExpressionStep \| ScriptStep \| Conclusion)[]` | 否 | `[]` | 步骤和结论节点，数组顺序用于编辑器和文档展示。 |

### WorkflowMetadata

| 字段 | 类型 | 必填 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| `name` | `string` | 是 | - | Workflow 展示名称。 |
| `code` | `string` | 否 | `""` | Workflow 编码，可用于展示或外部标识。 |
| `description` | `string` | 否 | `""` | Workflow 说明；创建 Workflow Skill 时要求非空。 |
| `symptom` | `string` | 否 | `""` | 问题现象，记录告警、用户感知或触发条件；不参与校验或 Skill 生成。 |
| `industry` | `string` | 否 | `""` | 适用产业或领域。 |
| `device` | `string` | 否 | `""` | 适用设备类型。 |
| `versions` | `string[]` | 否 | `[]` | 适用平台、软件或设备版本列表。 |

Workflow Metadata 不保存 Skill 的 owner、权限、Tags、生命周期或归档状态；这些信息以 Skill 为唯一真源。

## 通用参数与绑定

### Parameter

`Parameter` 是 Workflow 或 Collection 输入字段的声明，不保存运行时实际值。

| 字段 | 类型 | 必填 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| `id` | `string` | 是 | - | 参数身份，供 Binding 引用。 |
| `key` | `string` | 是 | - | 参数机器可读名称；在所属作用域内用于引用。当前编辑器新建参数默认为空。 |
| `name` | `string` | 是 | - | 参数展示名称；当前编辑器新建参数默认为空。 |
| `description` | `string` | 否 | `""` | 参数说明。 |
| `dataType` | `string` | 否 | `"string"` | 数据类型描述，例如 `string`、`integer`、`number`、`boolean`、`array`、`object`。Schema 不限制自定义字符串。 |
| `required` | `boolean` | 否 | `true` | 是否要求调用方提供该参数。 |

Workflow 编辑器新建全局输入时固定使用 `required: true`，且不提供切换控件；Schema 和 Import Bundle 仍接受 `required: false`，并按原值保存。Collection 输入仍可配置该字段。

### Binding

| 字段 | 类型 | 必填 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| `kind` | `string` | 是 | - | 绑定来源类型。当前领域规则支持 `workflow_input`、`collection_output` 和 `literal`。 |
| `reference` | `Record<string, string>` | 否 | `{}` | 来源引用，内容由 `kind` 决定。 |
| `value` | `any` | 否 | `null` | `literal` 绑定使用的固定值；其他绑定类型通常不使用。 |

常见引用形状：

| `kind` | `reference` | 含义 |
| --- | --- | --- |
| `workflow_input` | `{ "input_id": string }` | 引用 Workflow 全局输入。 |
| `collection_output` | `{ "call_id": string, "output_id": string }` | 引用当前步骤某个 Collection Call 的输出字段。 |
| `literal` | `{}` | 使用 `value` 中的 JSON 值。 |

## 设备角色

### DeviceRole

| 字段 | 类型 | 必填 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| `id` | `string` | 是 | - | 设备角色身份。 |
| `key` | `string` | 是 | - | 设备角色机器可读名称，在 Workflow 内唯一。 |
| `name` | `string` | 是 | - | 设备角色展示名称。 |
| `description` | `string` | 否 | `""` | 设备角色说明。 |
| `required` | `boolean` | 否 | `true` | 执行 Workflow 时是否必须提供该角色对应的设备。 |

## Collection

### CollectionMetadata

| 字段 | 类型 | 必填 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| `name` | `string` | 是 | - | Collection 展示名称。 |
| `description` | `string` | 否 | `""` | Collection 说明。 |
| `industry` | `string` | 否 | `""` | 适用产业或领域。 |
| `device` | `string` | 否 | `""` | 适用设备类型。 |
| `versions` | `string[]` | 否 | `[]` | 适用版本列表。 |
| `tags` | `string[]` | 否 | `[]` | Collection Catalog 标签。 |

### CollectionOutput

| 字段 | 类型 | 必填 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| `id` | `string` | 是 | - | 输出字段身份，供 `collection_output` Binding 引用。 |
| `key` | `string` | 是 | - | 输出字段机器可读名称。 |
| `description` | `string` | 否 | `""` | 输出字段说明。 |
| `dataType` | `string` | 否 | `"string"` | 输出数据类型，例如 `string` 或 `object`。 |

### CliOutputSample

| 字段 | 类型 | 必填 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| `id` | `string` | 是 | - | 回显示例身份。 |
| `name` | `string` | 是 | - | 回显示例名称。 |
| `stdout` | `string` | 否 | `""` | 作者用于预览的原始命令回显。 |
| `inputValues` | `Record<string, any>` | 否 | `{}` | 生成该回显示例时使用的输入值。 |

原始 `stdout` 和 `inputValues` 只用于作者预览，不会直接写入同步生成的 Skill 内容。

### CliCollectionSpec

| 字段 | 类型 | 必填 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| `commandTemplate` | `string` | 否 | `""` | 单行 CLI 命令模板；参数占位符由执行器或 Collection 机制解释。 |
| `outputSamples` | `CliOutputSample[]` | 否 | `[]` | CLI 回显示例。 |
| `collectionType` | `"cli"` | 否 | `"cli"` | Collection 类型常量，当前只支持 CLI。 |

### CollectionDefinition

| 字段 | 类型 | 必填 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| `id` | `string` | 是 | - | Collection 定义的稳定身份。 |
| `revision` | `integer` | 是 | - | Collection 定义修订号。 |
| `key` | `string` | 是 | - | Collection 的机器可读标识，在 Catalog 中使用。 |
| `metadata` | `CollectionMetadata` | 是 | - | Collection 展示和适用范围信息。 |
| `spec` | `CliCollectionSpec` | 是 | - | CLI 类型专属定义。 |
| `inputs` | `Parameter[]` | 否 | `[]` | 命令模板需要的输入参数。 |
| `outputs` | `CollectionOutput[]` | 否 | `[]` | 命令执行后产生的输出字段。 |
| `forkedFrom` | `VersionedRef \| null` | 否 | - | 该定义从哪个 Collection 版本复制而来。 |

### CollectionCall

`CollectionCall` 是某个步骤对 Collection 精确版本的一次调用。

| 字段 | 类型 | 必填 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| `id` | `string` | 是 | - | 调用身份，供 Binding 引用。 |
| `key` | `string` | 是 | - | 调用输出命名空间；为空时直接暴露输出字段。 |
| `name` | `string` | 是 | - | 调用展示名称；为空时回退为 Collection 名称。 |
| `definition` | `VersionedRef` | 是 | - | 被调用的 Collection `id + revision`。 |
| `deviceRoleId` | `string \| null` | 否 | - | 执行该调用时使用的设备角色；为空表示单设备。 |
| `sampleCount` | `integer` | 否 | `1` | 执行采集的次数。领域校验要求大于零。 |
| `inputBindings` | `Record<string, Binding>` | 否 | `{}` | 以 Collection 输入参数 ID 为 key 的绑定映射。 |

## 节点与跳转

### NodeRef

| 字段 | 类型 | 必填 | 含义 |
| --- | --- | --- | --- |
| `id` | `string` | 是 | 被引用节点的 ID。节点名称不参与引用。 |

### Transition

| 字段 | 类型 | 必填 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| `id` | `string` | 是 | - | 跳转身份；可供脚本执行器或外部工具引用。 |
| `target` | `NodeRef` | 是 | - | 跳转目标节点。 |
| `conditionText` | `string` | 否 | `""` | 面向作者和读者的条件说明；为空时界面显示“无条件”。 |
| `conditionExpression` | `string` | 否 | `""` | 条件表达式文本。编辑器提供变量补全，但具体解释仍由执行器或后续规则定义。 |

条件表达式编辑器使用以下作者侧变量命名空间：

- `global.<key>` 引用 Workflow 全局输入。
- `output.<callKey>.<outputKey>` 引用任意步骤的采集输出；调用 Key 为空时使用 `output.<outputKey>`。

补全候选包含所有步骤已经定义的采集输出，不依据拓扑区分前序或后续步骤。同名输出路径会按来源分别显示，但插入相同文本。该能力只辅助输入，不校验变量是否能在运行时取值，也不限制手动输入其他表达式。

输入变量片段或 `.` 后会自动展开候选，也可按 `Ctrl/Cmd+Space` 主动展开。使用方向键选择，按 `Tab` 或 `Enter` 补全，按 `Escape` 关闭；候选菜单未打开时，`Tab` 保持正常的表单焦点导航。

Transition 不包含 `name`、`description` 或 `key`。允许多条 Transition 指向同一目标；领域校验会拒绝跳转到不存在的节点。编辑器当前不提供步骤自循环创建入口。

### BaseStep

| 字段 | 类型 | 必填 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| `id` | `string` | 是 | - | 步骤身份。 |
| `name` | `string` | 是 | - | 步骤展示名称，可重复。 |
| `description` | `string` | 否 | `""` | 步骤说明。 |
| `isStart` | `boolean` | 否 | `false` | 是否为起始步骤。一个 Workflow 可以有多个起始步骤。 |
| `collectionCalls` | `CollectionCall[]` | 否 | `[]` | 当前步骤执行或使用的 Collection 调用。 |
| `topology` | `Transition[]` | 否 | `[]` | 当前步骤的“跳转到节点”列表。 |

### ExpressionStep

ExpressionStep 是条件表达式类型步骤，包含 BaseStep 的全部字段，并额外要求：

| 字段 | 类型 | 必填 | 含义 |
| --- | --- | --- | --- |
| `stepType` | `"expression"` | 是 | 节点类型判别字段。 |

### ScriptStep

ScriptStep 是脚本类型步骤，包含 BaseStep 的全部字段，并额外包含：

| 字段 | 类型 | 必填 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| `stepType` | `"script"` | 是 | - | 节点类型判别字段。 |
| `script` | `ScriptDraft \| null` | 否 | - | Python 脚本内容。目前 schema 仍允许为空。 |

### ScriptDraft

| 字段 | 类型 | 必填 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| `language` | `string` | 否 | `"python"` | 脚本语言标识。当前产品约定为 Python。 |
| `source` | `string` | 否 | `""` | 用户粘贴或编写的脚本源码。 |
| `options` | `Record<string, any>` | 否 | `{}` | 脚本相关扩展配置；当前没有固定字段语义。 |

当前 schema 只负责保存脚本文本，不负责执行、语法检查、沙箱配置、输入值解析或返回路径校验。

### Conclusion

| 字段 | 类型 | 必填 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| `id` | `string` | 是 | - | 结论节点身份。 |
| `name` | `string` | 是 | - | 结论展示名称，可重复。 |
| `rootCause` | `string` | 否 | `""` | 故障根因说明。 |
| `repairRecommendation` | `string` | 否 | `""` | 修复建议说明。 |
| `nodeType` | `"conclusion"` | 是 | - | 节点类型判别字段。 |

## 引用和数据流示例

下面的例子表示：Collection 输入参数 `interface_name` 绑定到 Workflow 全局输入。步骤本身不声明输入。

```json
{
  "id": "step-collect",
  "name": "采集接口状态",
  "description": "使用全局输入指定的接口名称执行采集。",
  "isStart": false,
  "stepType": "script",
  "script": {
    "language": "python",
    "source": "def main(context):\n    return 'transition-fault'",
    "options": {}
  },
  "collectionCalls": [
    {
      "id": "call-interface",
      "key": "interface",
      "name": "接口状态",
      "definition": { "id": "collection-interface", "revision": 1 },
      "sampleCount": 1,
      "inputBindings": {
        "collection-input-interface": {
          "kind": "workflow_input",
          "reference": { "input_id": "workflow-input-interface" }
        }
      }
    }
  ],
  "topology": [
    {
      "id": "transition-fault",
      "target": { "id": "conclusion-fault" },
      "conditionText": "检测到接口故障",
      "conditionExpression": ""
    }
  ]
}
```

`CollectionCall.inputBindings` 的键必须是被调用 Collection 的输入参数 ID。Binding 只描述来源关系；当前后端不会执行命令或计算表达式。

## 相关接口

获取某个 Skill 的完整 Workflow 文档：

```http
GET /api/skills/{skill_id}/workflow
```

完整 Bundle 位于响应的 `document` 字段中。该响应还会提供当前 `revision`、`document_schema_version`、领域校验结果、同步状态和当前 actor 的 capabilities。

获取全局 Collection Catalog：

```http
GET /api/skills/{skill_id}/workflow/collections
```

Catalog 列表不替代 `document.collectionSnapshots`；Workflow 保存和同步使用的是 Bundle 内的精确快照。

从旧格式导入时不要直接拼装持久化 Bundle 或 `collection_changes`，应使用专用接口：

```http
POST /api/skills/{skill_id}/workflow/import
```

Import Bundle 不包含 Workflow/Collection 的持久化 ID 和 revision。详细格式、转换算法和 Agent 脚本骨架见 [workflow-import-agent-guide.md](workflow-import-agent-guide.md)。
