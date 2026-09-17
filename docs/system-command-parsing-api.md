# 系统命令回显解析接口使用指导

本接口接收具体命令与已有回显，自动选择系统命令库中的 TTP 模板并返回 JSON 结果。它不连接设备、不执行命令，也不创建工作流、采集记录或访问统计。

## 1. 准备系统命令

在后台“系统命令库”创建并启用命令，填写表达式、TTP 模板和输出 Schema。模板为空的记录不参与最终选择；回显示例只是展示内容，不会替代请求中的 `echo`。

示例表达式：`show interfaces <interface>`。

示例 TTP（注意 `packets` 行前有一个空格，与回显一致）：

```xml
<group name="interfaces*">
Interface {{ name }} is {{ state }}
 packets {{ packets | to_int }}
</group>
```

示例输出 Schema：

```json
{
  "type": "object",
  "properties": {
    "interfaces": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "name": {"type": "string"},
          "state": {"type": "string"},
          "packets": {"type": "integer"}
        },
        "required": ["name", "state", "packets"],
        "additionalProperties": false
      }
    }
  },
  "required": ["interfaces"],
  "additionalProperties": false
}
```

## 2. 请求接口

`POST /api/command-library/parse`，`Content-Type: application/json`。

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| input | string，必填 | 单条具体命令，不包含设备提示符；最长 4,000 字符，去除首尾空白后不能为空 |
| echo | string，必填 | 原始回显，保留空格和换行；允许空字符串，UTF-8 不超过 1 MiB |

不接受额外字段、命令 ID、客户端模板、设备版本或用户命令库选项。`input` 中间不能含换行或 NUL；它应是实际命令而非工作流的动态参数模板。接口沿用普通 REST actor 身份依赖，无需后台密钥或 MCP Cookie。可选使用现有 `X-SkillHub-Actor` 请求头；未传时遵循部署的默认身份规则。

curl 示例（本地 API 端口为 8003；其他部署替换地址）：

```sh
curl -X POST http://127.0.0.1:8003/api/command-library/parse \
  -H 'Content-Type: application/json' \
  --data-raw '{"input":"show interfaces eth0","echo":"Interface eth0 is up\n packets 42\n"}'
```

Windows PowerShell 可使用下面的 Python 示例，避免 Shell JSON 引号差异。仅使用 Python 标准库：

```python
import json
from urllib.request import Request, urlopen
from urllib.error import HTTPError

payload = {
    "input": "show interfaces eth0",
    "echo": "Interface eth0 is up\n packets 42\n",
}
request = Request(
    "http://127.0.0.1:8003/api/command-library/parse",
    data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
    headers={"Content-Type": "application/json"},
    method="POST",
)
try:
    with urlopen(request, timeout=15) as response:
        print(json.dumps(json.load(response), ensure_ascii=False, indent=2))
except HTTPError as error:
    print(error.code, error.read().decode("utf-8"))
```

## 3. 返回结果与诊断

示例返回（命令 ID 由系统分配）：

```json
{
  "command": {
    "id": "system-command_example",
    "key": "interfaces",
    "name": "接口状态",
    "expression": "show interfaces <interface>"
  },
  "result": {
    "interfaces": [{"name": "eth0", "state": "up", "packets": 42}]
  },
  "validation": {"valid": true, "warnings": []}
}
```

`result` 只去除 TTP 的模板和输入包装层，不展平业务数组，也不合并多个对象。没有分组的多行模板可能返回数组；为了符合系统命令的 object 根 Schema，建议用命名 group 表达业务结构。

Schema 不一致仍返回 HTTP 200 和原始 `result`，`validation.valid=false`。不会把字符串数字转成整数、补默认值或删除额外字段。转换应由模板显式指定，例如 `to_int`。

提醒结构：`{"code":"SCHEMA_TYPE_MISMATCH","path":"/interfaces/0/packets","message":"结果类型不符合 integer。"}`。
`path` 使用 JSON Pointer；空字符串表示根，字段名中的 `/`、`~` 分别编码为 `~1`、`~0`。

| 提醒码 | 含义 |
| --- | --- |
| SCHEMA_TYPE_MISMATCH | 类型与 Schema 不一致，包括 boolean 不能作为 integer |
| SCHEMA_REQUIRED | 缺少必填字段 |
| SCHEMA_ADDITIONAL_PROPERTY | Schema 禁止的额外字段 |
| TTP_EMPTY_RESULT | 没有提取到内容，请检查回显与模板 |

空回显通常返回 `{}`；它仍按 Schema 校验。`validation.valid` 仅表示 Schema 是否符合，空结果提醒本身不改变该值。

## 4. 命令选择与错误处理

仅匹配已启用的系统规则，采用完整匹配，排除名称/Key 搜索、前缀匹配和用户命令。按记录 ID 去重，再从具有非空 TTP 的候选中比较现有匹配分和已消费 token 数。最佳项并列时拒绝解析，返回候选供管理员调整；不会按名称或 ID 任意选择。

未配置版本筛选。同一命令在不同设备或版本的规则上同分命中，也返回歧义。选定的模板无效或解析失败时不会退回低分模板。

错误包含 `detail` 和稳定的 `code`；歧义另含 `candidates`，请求格式错误另含 `field_errors`。错误不返回回显、模板或内部堆栈。

| HTTP | code | 处理建议 |
| --- | --- | --- |
| 422 | INVALID_REQUEST | 检查字段、类型、单行命令及长度 |
| 413 | ECHO_TOO_LARGE | 回显 UTF-8 超过 1 MiB，缩小单次输入 |
| 404 | COMMAND_NOT_FOUND | 检查完整命令表达式与启用状态 |
| 409 | COMMAND_AMBIGUOUS | 根据候选调整重叠规则 |
| 400 | TTP_TEMPLATE_MISSING | 给匹配命令配置 TTP |
| 400 | TTP_TEMPLATE_INVALID | 修正模板语法或移除不支持的能力 |
| 400 | TTP_PARSE_FAILED | 检查模板编译、转换参数与回显格式；不能把部分结果视为成功 |
| 504 | TTP_PARSE_TIMEOUT | 单次解析超过 5 秒，进程已终止；简化正则或输入 |

原有身份依赖校验失败仍遵循普通 REST 身份错误格式。

## 5. 模板支持范围

依赖锁定为官方 `ttp==0.10.1`。支持裸匹配文本、单个无属性 `<template>` 包装，以及嵌套 `<group>`。group 仅允许 `name` 和 `method="group|table"`；`name="interfaces*"` 表示数组分组，支持命名嵌套及动态分组路径。

匹配变量必须为标识符；管道允许：

- 模式：`WORD`、`PHRASE`、`ROW`、`ORPHRASE`、`DIGIT`、`IP`、`PREFIX`、`IPV6`、`PREFIXV6`、`MAC`、`re`。
- 控制：`_start_`、`_end_`、`_line_`、`_exact_`、`_exact_space_`、`ignore`。
- 转换和字符串：`to_int`、`to_float`、`to_str`、`to_list`、`to_unicode`、`lower`、`upper`、`strip`、`lstrip`、`rstrip`、`split`、`join`、`replace`。
- 条件：`contains`、`exclude`、`equal`、`notequal`、`isdigit`、`notdigit`、`contains_re`、`exclude_re`、`startswith_re`、`endswith_re`、`notstartswith_re`、`notendswith_re`。
- 值和聚合：`set`、`default`、`joinmatches`。

参数只能是字面量，例如 `re("[0-9]+")`、`replace("down", "offline")`；不能写 Python 调用、属性访问或变量求值。沿用 TTP 管道分隔限制，参数中的正则 `|` 不支持，可改用字符类或多个模式。XML 特殊字符需要转义。

禁止 macro、vars、lookup、input、output、extend、多模板、XML 声明/实体声明/注释、外部文件及网络输入、输出回调和自定义函数。模板文本最多 50,000 字符。只执行数据库中保存的模板，不接受客户端传入模板；命令捕获值不注入模板。

每次解析使用独立子进程与内存文本 loader，文件路径形式的回显也只当作文字。5 秒预算包含进程启动、模板检查与解析；超时强制终止并回收。结果必须能序列化成标准 JSON，不允许 NaN/Infinity。TTP 的解析错误不会仅写日志后返回成功。

## 6. 开发与部署

更新依赖后运行 `cd apps/backend && uv sync --locked`，重启现有 API；无需数据库迁移。API 文档可在 `/docs` 的命令解析路由查看。接口不新增执行器能力，不改变原有工作流、系统命令保存或 MCP 工具契约。
