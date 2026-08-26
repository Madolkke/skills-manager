# Workflow 文档 Schema

本文档描述 SkillHub 当前 Workflow 文档格式 **schema v5**。它是 `WorkflowBundle` 的持久化结构，字段名使用 API 中的 camelCase 形式。

权威实现：

- 后端结构定义：`apps/backend/skillhub/models/rules/workflows/schema.py`
- 前端镜像类型：`apps/frontend/src/types/workflow.ts`
- 领域校验：`apps/backend/skillhub/models/rules/workflows/validation.py`
- 日志 SQL 规则：`apps/backend/skillhub/models/rules/workflows/log_sql.py`
- 日志列目录：`apps/backend/skillhub/models/rules/workflows/log_schema.py`
- 配置匹配语法：[Workflow 配置匹配 Collection](workflow-config-matching.md)

## 基本规则

- `document_schema_version` 存在数据库 `workflows` 表中，不写入 Bundle 内部；当前值为 `5`。
- v3 文档会先沿用既有结构迁移，v4 文档可直接按 v5 模型读取；旧文档只在下一次正常保存时写为 v5。v1、v2 和未知版本仍被拒绝。
- 所有对象禁止未知字段，字段名使用严格类型校验。
- Python 字段名通过 alias 转换为 camelCase，例如 `step_type` 对应 `stepType`。
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
| `required` | `boolean` | 否 | `true` | 是否要求调用方提供该参数。 |
| `schema` | `WorkflowJsonSchema` | 是 | - | 参数结构；展示名称和说明分别位于 `schema.title`、`schema.description`。 |

Schema 和导入接口保留 `required`。编辑器新建 Workflow 输入、Collection 输入和 Collection 输出时均写入 `true`，历史 `false` 值保持兼容。

### WorkflowJsonSchema

Workflow 字段采用 JSON Schema Draft 2020-12 的受控子集：

- 标量：`string`、`integer`、`number`、`boolean`。
- 对象：递归 `properties`、`required`，新对象固定 `additionalProperties: false`。
- 数组：必须声明递归 `items`，因此可表达对象数组和多维数组。
- 所有有类型节点可声明 `title` 和 `description`。
- 暂不接受 `null`、`enum`、约束关键字、`$ref`、组合或条件 Schema。

从 v3 迁移且无法推断元素结构的 `array`/`object` 会带 `x-skillhub-legacy-loose: true`，编辑器显示兼容警告；新建 Schema 不能产生该标记。

编辑器按复杂度提供两种入口：

- Workflow 全局输入、Collection 输入和 Collection 输出在界面中不提供“是否必填”开关，新建字段默认写入 `required: true`；为保持文档兼容，已有 `required: false` 不会被普通行内编辑自动覆盖。
- `string`、`integer`、`number`、`boolean` 和字符串数组在字段行内编辑类型、显示名称及说明。字符串数组仍保存为 `type: "array"` 且 `items.type: "string"`，不是新的 Schema 类型。
- `object` 以及 items 不是 string 的其他数组统一显示为“复杂对象”，通过 Schema 弹窗维护 object/array 根类型和递归子结构。
- 复杂 Schema 弹窗中的对象属性统一视为必填，不提供单独开关；确认弹窗时会递归将该 Schema 内所有对象属性写入对应 `required`。取消弹窗或未打开历史 Schema 均不会触发该规范化。
- 复杂对象切换为标量或字符串数组会删除嵌套结构，编辑器必须在修改前要求确认。标量切换为复杂对象时默认创建 `additionalProperties: false` 的空 object。
- 只要数组的 `items.type` 为 `string`，包括仍带 legacy loose 标记的文档，编辑器都按字符串数组展示；除非作者主动切换类型，否则保存不会移除兼容标记。

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

`collection_output` 只允许引用同一步骤中排在当前调用之前的输出，并按递归 Schema 检查兼容性；`integer` 可以赋给 `number`。固定值不匹配只产生 warning。

条件表达式使用 Python `eval` 语法，根变量为 `inputs`、`outputs` 和配置匹配专用的 `config`。单次采集按对象访问，例如 `outputs.inventory.status`；`sampleCount > 1` 时调用结果为数组，字段路径必须先指定结果下标，例如 `outputs.inventory[0].status`。下标支持零基正数、Python 负数、动态整数和切片。历史多次采集表达式缺少下标时保留原文并产生 warning，不自动选择某次结果。

表达式契约版本为 `contractVersion = 2`。`environment.outputs` 的命名采集使用 `{ sampleCount, fields }`，无 `callKey` 的直接输出使用 `{ sampleCount, schema }` 表示根值；旧字段 map 继续按单次采集兼容。函数与只读方法白名单由 `GET /api/workflow-expression-contract` 提供，单条 `POST /api/workflow-expression-validations` 与批量 `POST /api/workflow-expression-validations/batch` 返回类型和位置诊断。HTTP 接口只执行 AST 与类型检查，不执行 expression evaluator。采集下标诊断汇总为 Workflow warning，不阻止保存或同步。

表达式函数由全局函数库提供。函数名和参数名必须是非关键字、非私有的 Python 标识符；参数 Schema 决定位置参数顺序、关键字参数和必填参数，返回 Schema 决定静态返回类型。函数体作为纯文本保存，不在 Workflow 写作或执行阶段解析、执行；删除函数后，历史调用保留原文并在后续校验中报告 `UNREGISTERED_CALL`。

## 设备角色

### DeviceRole

| 字段 | 类型 | 必填 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| `id` | `string` | 是 | - | 设备角色身份。 |
| `key` | `string` | 是 | - | 设备角色机器可读名称，在 Workflow 内唯一，也是表达式稳定路径段；必须是非私有 Python 标识符。 |
| `name` | `string` | 是 | - | 设备角色展示名称；修改不会改变已有表达式路径。 |
| `description` | `string` | 否 | `""` | 设备角色说明。 |
| `required` | `boolean` | 否 | `true` | 执行 Workflow 时是否必须提供该角色对应的设备。 |
| `schema` | `WorkflowJsonSchema \| null` | 否 | - | 可选的设备参数 object Schema；合法的递归属性通过 `topo.devices.<roleKey>.<property>` 访问。 |

设备角色 Schema 只提供作者侧表达式的类型信息，可用于条件判定、条件说明模板、结论模板和变量查看器；不会向执行器或调试请求注入运行时设备参数值。未配置或不合法的 Schema 不生成 `topo.devices` 变量。

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

`outputs[]` 表示一条命令的根属性集合。系统或用户命令库的根 `outputSchema.properties` 会在物化为 Collection 时分别转换为这些输出项；已有 Workflow Collection 不会因为某个输出项的 Schema 是 object 或 array 而再次拆分。表达式中无 `callKey` 时使用 `outputs.<key>`，有 `callKey` 时使用 `outputs.<callKey>.<key>`，根属性的 object/array 子结构继续递归访问。

| 字段 | 类型 | 必填 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| `id` | `string` | 是 | - | 输出字段身份，供 `collection_output` Binding 引用。 |
| `key` | `string` | 是 | - | 输出字段机器可读名称。 |
| `required` | `boolean` | 否 | `true` | 输出字段是否保证存在；v3 输出迁移后为 `false`。 |
| `schema` | `WorkflowJsonSchema` | 是 | - | 输出结构；展示名称和说明位于 Schema 内。 |

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
| `collectionType` | `"cli"` | 是 | - | 严格联合的 CLI 判别字段。 |
| `commandParameterSyntax` | `"angle-v1"` | 否 | - | 启用 `<name>` 命令参数语法。旧定义保持缺失，首次修改命令时写入。 |

启用 `angle-v1` 后，名称必须是合法且非关键字的 Python 标识符。同名占位符只对应一个 Collection 输入；命令合法时，编辑器自动增加同名 `string` 输入，并在占位符删除时清理对应输入、样例输入值和调用绑定。暂态非法命令保留原文并产生校验错误，不执行破坏性同步。当前版本不支持字面尖括号转义。

### LogAggregationQuery

| 字段 | 类型 | 必填 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| `id` | `string` | 是 | - | 查询身份，在当前日志 Collection 内唯一。 |
| `name` | `string` | 是 | - | 作者可见的查询名称。 |
| `sql` | `string` | 否 | `""` | DuckDB SQL；只允许一条 `SELECT` 或 `WITH ... SELECT`。空值会产生领域校验错误。 |
| `outputIds` | `string[]` | 否 | `[]` | 本查询负责产生的 `CollectionOutput.id` 列表。 |

### LogOutputSample

| 字段 | 类型 | 必填 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| `id` | `string` | 是 | - | 日志样例身份。 |
| `name` | `string` | 是 | - | 日志样例名称。 |
| `text` | `string` | 否 | `""` | 原始日志文本；仅供作者参考，不解析、不校验、不参与运行。 |

### LogCollectionSpec

| 字段 | 类型 | 必填 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| `collectionType` | `"log"` | 是 | - | 严格联合的日志判别字段。 |
| `sqlDialect` | `"duckdb"` | 是 | - | 首版固定 SQL 方言。 |
| `queries` | `LogAggregationQuery[]` | 否 | `[]` | 标量聚合查询列表。 |
| `outputSamples` | `LogOutputSample[]` | 否 | `[]` | 原始日志样例。 |

日志 Collection 的 inputs/outputs 只允许 `string`、`integer`、`number` 和 `boolean`，每个输出必须且只能归属一条查询。v5 的 `sqlDialect` 必须显式为 `duckdb`；v3/v4 通过迁移入口读取时会显式补齐该字段。固定 `logs`/`params` 表、alias 映射、SQL AST 门禁和运行侧责任见 [Workflow 日志 SQL 聚合](workflow-log-sql-aggregation.md)。

### ConfigCollectionSpec

| 字段 | 类型 | 必填 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| `collectionType` | `"config"` | 是 | - | 严格联合的配置匹配判别字段。 |
| `config` | `ConfigRoot` | 是 | - | 由执行器从设备完整配置中匹配的递归命令树。 |

`ConfigCommand` 必须包含合法 Python 标识符形式的 `name`、单行 `pattern`、`captures` 和 `children`。`unique=false` 的命令结果为数组；捕获字段只允许四种标量 Schema，配置结果通过 `config` 表达式根访问。配置调用固定 `sampleCount=1`，完整语法见 [Workflow 配置匹配 Collection](workflow-config-matching.md)。

### CollectionDefinition

| 字段 | 类型 | 必填 | 默认值 | 含义 |
| --- | --- | --- | --- | --- |
| `id` | `string` | 是 | - | Collection 定义的稳定身份。 |
| `revision` | `integer` | 是 | - | Collection 定义修订号。 |
| `key` | `string` | 是 | - | Collection 的机器可读标识，在 Catalog 中使用。 |
| `metadata` | `CollectionMetadata` | 是 | - | Collection 展示和适用范围信息。 |
| `spec` | `CliCollectionSpec \| LogCollectionSpec \| ConfigCollectionSpec` | 是 | - | 以 `collectionType` 判别的严格类型专属定义。 |
| `inputs` | `Parameter[]` | 否 | `[]` | 命令模板需要的输入参数。 |
| `outputs` | `CollectionOutput[]` | 否 | `[]` | 命令执行后产生的输出字段。 |
| `forkedFrom` | `VersionedRef \| null` | 否 | - | 该定义从哪个 Collection 版本复制而来。 |
| `sourceSystemCommandId` | `string \| null` | 否 | - | 仅 CLI 系统命令物化后的来源身份。此类定义只读，保存时由后端同步最新系统命令；导出时移除。 |

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

日志 Collection 调用固定 `sampleCount = 1` 且不支持 `deviceRoleId`；配置 Collection 调用固定 `sampleCount = 1`。违反这些规则仍可保存为草稿，但会产生 validation error 并阻止同步。

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
| `conditionText` | `string` | 否 | `""` | 面向作者和读者的条件说明；支持普通文本与 `{{ expression }}` 模板，模板原文保存，为空时界面显示“无条件”。 |
| `conditionExpression` | `string` | 否 | `""` | 条件表达式文本。编辑器提供变量补全，但具体解释仍由执行器或后续规则定义。 |

条件表达式编辑器使用以下作者侧变量命名空间：

- `inputs.<key>` 引用 Workflow 全局输入。
- `topo.devices.<roleKey>.<property>` 引用设备角色的参数 Schema。角色和属性 key 必须是不以下划线开头的 Python 标识符。
- `outputs.<callKey>.<outputKey>` 引用当前步骤或任一传递前序步骤的采集输出；调用 Key 为空时，Collection 的每个合法根输出字段直接使用 `outputs.<outputKey>`。

历史文档中使用 `global.<key>` 或 `output.<...>` 的表达式应在保存前迁移到上述 `inputs`/`outputs` 根名称；新文档和补全不会再生成旧写法。

补全和类型检查按 Workflow 图反向遍历，包含当前步骤及所有传递前序步骤，不包含未来或无图连接的步骤；结果按文档节点顺序稳定合并。多次采集先补全 `outputs.<callKey>[0].<field>`，没有 `callKey` 的非法多次采集不进入直接输出环境，切片路径不提供字段补全。带 `callKey` 的同名命名空间保持 first-wins 兼容行为；无 `callKey` 的直接输出若与全局输入或同一可见环境中的其他直接输出重名，则报告 `UNSCOPED_OUTPUT_CONFLICT` 且不生成该字段补全。Collection Input 的 `collection_output` Binding 可引用当前调用之前或传递前序步骤中的采集，当前步骤后续、未来和无图连接步骤不可引用。

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
| `severity` | `"info" \| "warning" \| "error" \| "critical"` | 否 | `"info"` | 结论严重等级。历史文档缺失时归一化为信息。 |
| `rootCause` | `string` | 否 | `""` | 故障根因说明。 |
| `repairRecommendation` | `string` | 否 | `""` | 修复建议说明。 |
| `nodeType` | `"conclusion"` | 是 | - | 节点类型判别字段。 |

`conditionText`、`rootCause` 和 `repairRecommendation` 支持 `{{ expression }}` 模板。条件说明使用所属步骤的表达式环境；结论模板使用能够沿拓扑到达该结论的步骤环境。模板原文随 Workflow 保存，不在写作侧或执行器中展开；表达式只能引用对应环境中的输出、全局输入、设备角色和配置匹配，未来或无连接步骤不可见。模板可包含多个插值和普通文本，不支持控制流、循环或嵌套模板。

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

获取日志 SQL 的固定列目录：

```http
GET /api/workflow-log-schema
```

该接口返回 schema v5、DuckDB 方言、`logs`/`params` 表名及六个固定日志列。完整响应和 SQL 契约见 [Workflow 日志 SQL 聚合](workflow-log-sql-aggregation.md)。

从旧格式导入时不要直接拼装持久化 Bundle 或 `collection_changes`，应使用专用接口：

```http
POST /api/skills/{skill_id}/workflow/import
```

Import Bundle 不包含 Workflow/Collection 的持久化 ID 和 revision。详细格式、转换算法和 Agent 脚本骨架见 [workflow-import-agent-guide.md](workflow-import-agent-guide.md)。

当前已保存 Workflow 也可以导出为同一种可移植格式：

```http
GET /api/skills/{skill_id}/workflow/export
```

导出只包含 `document.collectionSnapshots` 中被 Call 实际引用的精确版本，并将持久化引用改写为请求内 `localId`。导出文件不包含数据库身份、revision 历史、权限、Tags 或未引用的全局 Catalog 定义，因此适合跨实例迁移，不等同于数据库备份。编辑器存在未保存修改时，前端要求先保存再执行导入或导出。
