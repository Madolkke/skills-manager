# Workflow 日志 SQL 聚合

本文定义 Workflow schema v5 中 `log` Collection 的作者契约。日志 Collection 面向已经被运行侧整理成结构化日志表的数据，通过 DuckDB SQL 产出少量标量结果，供步骤条件和后续 Collection 使用。

SkillHub 只保存日志 Collection 契约、提供固定列目录并执行 SQL AST 静态校验。SkillHub 不接收或持久化日志 DataFrame，不执行 SQL，也不提供日志采集、预览、运行历史或外部执行器接口。

## 1. 适用场景

日志 SQL 聚合适合把大量日志归约为工作流可消费的确定字段，例如：

- 指定时间范围内的错误数量；
- 是否出现某类模块或关键字；
- 最近一次异常时间、设备或摘要；
- 不同严重等级的计数和布尔判断；
- 基于显式 Workflow 输入过滤设备、模块或时间范围。

输出必须是 `string`、`integer`、`number` 或 `boolean` 标量。需要返回明细行、数组、对象、DataFrame 或原始日志文件的场景不属于本契约。

## 2. Collection 契约

`CollectionDefinition.spec` 是以 `collectionType` 为判别字段的严格联合。日志分支固定为：

```text
LogCollectionSpec
  collectionType: "log"
  sqlDialect: "duckdb"
  queries: LogAggregationQuery[]
  outputSamples: LogOutputSample[]

LogAggregationQuery
  id: string
  name: string
  sql: string
  outputIds: string[]

LogOutputSample
  id: string
  name: string
  text: string
```

未知字段会被拒绝。`sqlDialect` 首版只接受 `duckdb`，不能省略或改成其他方言。`outputIds` 保存 `CollectionOutput.id`，SQL 顶层列 alias 使用对应的 `CollectionOutput.key`；ID 和 Key 不能混用。

完整定义示例：

```json
{
  "id": "collection-log-health",
  "revision": 1,
  "key": "log_health",
  "metadata": {
    "name": "日志健康度聚合",
    "description": "统计给定设备和时间范围内的异常日志。",
    "industry": "网络",
    "device": "交换机",
    "versions": [],
    "tags": ["log"]
  },
  "spec": {
    "collectionType": "log",
    "sqlDialect": "duckdb",
    "queries": [
      {
        "id": "query-errors",
        "name": "异常统计",
        "sql": "SELECT COUNT(*) FILTER (WHERE severity = 'error') AS error_count, COALESCE(MAX(brief) FILTER (WHERE severity = 'error'), '') AS latest_error_brief\nFROM logs\nCROSS JOIN params\nWHERE device = params.\"device-name\"\n  AND event_time >= TRY_CAST(params.\"start.time\" AS TIMESTAMP)",
        "outputIds": ["output-error-count", "output-latest-brief"]
      }
    ],
    "outputSamples": [
      {
        "id": "sample-errors",
        "name": "设备出现两条错误日志",
        "text": "2026-08-01 10:00:00 device-a routing error ..."
      }
    ]
  },
  "inputs": [
    {
      "id": "input-device",
      "key": "device-name",
      "required": true,
      "schema": { "type": "string", "title": "设备名称", "description": "要检查的设备。" }
    },
    {
      "id": "input-start-time",
      "key": "start.time",
      "required": true,
      "schema": { "type": "string", "title": "开始时间", "description": "可转换为 TIMESTAMP 的时间文本。" }
    }
  ],
  "outputs": [
    {
      "id": "output-error-count",
      "key": "error_count",
      "required": true,
      "schema": { "type": "integer", "title": "错误数量", "description": "错误级别日志数量。" }
    },
    {
      "id": "output-latest-brief",
      "key": "latest_error_brief",
      "required": true,
      "schema": { "type": "string", "title": "最近错误摘要", "description": "没有错误时为空字符串。" }
    }
  ]
}
```

## 3. 固定运行表

未来运行侧必须为每条查询注册 `logs` 和 `params` 两张表。表名固定且区分于作者自定义 CTE。

### `logs`

| 列 | DuckDB 类型 | 可空 | 语义 |
| --- | --- | --- | --- |
| `event_time` | `TIMESTAMP` | 是 | 日志事件时间，不约定时区转换。 |
| `device` | `VARCHAR` | 是 | 日志来源设备。 |
| `module` | `VARCHAR` | 是 | 产生日志的模块。 |
| `severity` | `VARCHAR` | 是 | 日志严重等级。 |
| `brief` | `VARCHAR` | 是 | 日志摘要。 |
| `body` | `VARCHAR` | 是 | 原始日志正文。 |

所有列均允许为 `NULL`。作者必须在 SQL 中按业务语义处理空值，不能假定解析器一定填充某一列。

### `params`

`params` 是恰好一行的参数表，每一列来自当前 Collection 显式声明的一个输入：

- 只允许 `string`、`integer`、`number`、`boolean` 四种输入 Schema；
- 运行侧负责把四种 Schema 映射成 DuckDB 可读取的列值；
- 参数通过 `params."原始 key"` 访问；包含 `.`、`-` 或其他需要转义的字符时必须使用双引号；
- 不使用 `{{ value }}`、`${value}` 等模板插值；
- 不注入“问题时间段”、当前设备或其他隐式上下文。需要的值必须由 Collection input 和 `CollectionCall.inputBindings` 明确声明。

## 4. 查询与输出规则

一个日志 Collection 可以配置多条查询。每条查询在未来运行时都必须返回恰好一行，多条查询的列结果按输出 Key 扁平合并。

作者必须同时满足：

1. 每个 `CollectionOutput` 必须且只能出现在一条查询的 `outputIds` 中。
2. `outputIds` 引用的输出必须存在。
3. SQL 顶层投影列必须逐一使用显式 `AS` alias。
4. alias 必须与所声明输出的 `CollectionOutput.key` 完全一致。
5. 输出 Schema 只允许四种标量类型。
6. 运行结果不能为 `NULL`；空集合需要作者使用 `COALESCE`、`COUNT` 或其他明确策略处理。

SkillHub 不静态证明 SQL 实际返回一行、DuckDB 表达式类型与输出 Schema 一致，或运行结果一定非空。这三项是未来运行侧的契约检查责任。

## 5. SQL 静态校验

SkillHub 使用 [SQLGlot 的 DuckDB AST API](https://sqlglot.com/sqlglot) 解析查询，只做无副作用的静态门禁：

- 只允许一条 `SELECT` 或 `WITH ... SELECT`；
- 只允许读取 `logs`、`params` 和本条语句定义的 CTE；
- 拒绝 DDL、DML、`ATTACH`、扩展加载、文件读取、外部表和多语句；
- 顶层禁止 `*` 和隐式输出名，每列必须显式 alias；
- 校验对 `logs` 固定列和 `params` 输入 Key 的引用；
- 校验 alias、`outputIds` 和 Collection 输出之间的对应关系；
- 按文档顺序产生确定的校验问题。

静态校验不会执行 SQL，也不会把 SQLGlot 当成运行引擎。保存只要求 JSON 结构符合严格模型；SQL 和领域错误允许随草稿保存，但会阻止 Workflow 同步。

代表性错误码：

| 错误码 | 含义 |
| --- | --- |
| `LOG_QUERY_SQL_INVALID` | SQL 为空、语法错误或不是允许的查询语句。 |
| `LOG_QUERY_MULTIPLE_STATEMENTS` | SQL 包含多条语句。 |
| `LOG_QUERY_FORBIDDEN_SOURCE` | 引用了外部表、文件、扩展或未允许的数据源。 |
| `LOG_QUERY_UNKNOWN_COLUMN` | 引用了未知的 `logs` 列或 `params` 输入列。 |
| `LOG_QUERY_OUTPUT_ALIAS_MISMATCH` | 顶层 alias 与查询声明的输出 Key 不一致。 |
| `LOG_QUERY_OUTPUT_NOT_ASSIGNED` | 输出未归属查询、重复归属或引用不存在。 |
| `LOG_INPUT_SCHEMA_NOT_SCALAR` | 日志输入不是四种标量 Schema。 |
| `LOG_OUTPUT_SCHEMA_NOT_SCALAR` | 日志输出不是四种标量 Schema。 |
| `LOG_CALL_DEVICE_ROLE_UNSUPPORTED` | 日志调用配置了设备角色。 |
| `LOG_CALL_SAMPLE_COUNT_UNSUPPORTED` | 日志调用的 `sampleCount` 不为 `1`。 |

## 6. 调用约束

日志 Collection 仍通过普通 `CollectionCall` 加入 Step，并复用输入 Binding 和输出路径规则。日志调用额外要求：

- `sampleCount` 固定为 `1`；
- `deviceRoleId` 必须为空；
- 新建调用时编辑器自动采用上述值；
- 无效值可以作为草稿保存，但会产生 validation error 并阻止同步。

日志数据集本身不通过 Binding 传入。运行侧在执行日志 Collection 时提供本次运行的全量 `logs` 表，并根据普通 Binding 生成 `params` 单行表。

## 7. 日志样例

`LogOutputSample` 只保存 `id`、`name` 和原始 `text`。它用于作者记录典型日志片段：

- SkillHub 不解析或校验 `text`；
- 样例不参与 SQL 静态校验；
- 样例不参与未来运行；
- 生成的 Skill 文档只列出样例名称，不输出原始正文，避免把敏感日志复制到发布内容。

## 8. 列目录 API

编辑器通过以下接口读取固定契约，不在组件中自行定义另一份列语义：

```http
GET /api/workflow-log-schema
```

响应示例：

```json
{
  "document_schema_version": 5,
  "dialect": "duckdb",
  "logs_table": "logs",
  "params_table": "params",
  "columns": [
    {
      "name": "event_time",
      "duckdb_type": "TIMESTAMP",
      "nullable": true,
      "title": "时间",
      "description": "日志事件时间（无时区）"
    }
  ]
}
```

正式响应始终返回六列。该接口是全局只读契约接口，使用 SkillHub 标准 actor context，不绑定某个 Skill 或 Collection 权限。

## 9. schema v5 与兼容

- 新保存和新导入的 Workflow、Collection revision 写入 `document_schema_version = 5`。
- v3 文档先沿用既有 v3 到 v4 的结构迁移，再按 v5 严格模型读取；v4 文档也可直接读取。
- 读取旧文档不会重写 JSON、增加 Workflow/Collection revision 或修改 digest。
- 旧文档下一次被正常保存或创建新 Collection revision 时写为 v5。
- Alembic `0005_workflow_log_sql_v5` 只更新新记录的默认版本和迁移入口，不批量改写历史 JSON。
- 旧 CLI spec 和生成内容保持兼容；v5 只是为 `CollectionDefinition.spec` 增加严格 `log` 分支。

`GET /api/skills/{skill_id}/workflow/formatted` 继续返回当前规范化 Workflow 文档；日志 spec 按 v5 结构保留。Workflow Skill Generator 会展示 SQL、查询到输出的映射和样例名称，但不会输出日志样例正文。面向外部执行器的 `/workflow/executor` 首版仍不支持日志 Collection，遇到日志定义时返回明确的不支持错误，而不是尝试转换。

## 10. 运行侧边界

未来运行侧接入 v5 时必须负责：

- 把全量日志数据注册为上述 `logs` 表；
- 解析普通 Binding 并注册单行 `params`；
- 在隔离的 DuckDB 环境执行已经通过静态门禁的 SQL；
- 验证每条查询恰好一行、列类型符合输出 Schema 且值不为 `NULL`；
- 合并多条查询结果并按 Collection 输出 Key 发布；
- 设置资源、超时、内存和查询并发限制。

本期明确不引入 `pandas` 或 DuckDB 运行依赖，不新增数据库表、日志上传 API、SQL 预览/执行 API、运行历史、缓存或外部执行器映射。
