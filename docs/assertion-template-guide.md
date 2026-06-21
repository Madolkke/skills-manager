# 判断模板实现指南

本文档用于指导开发新的测评判断模板。判断模板是每个测试步骤的判定逻辑：Runner 将输入发送给 Opencode，等待本轮 Agent 停止后，把 Agent 输出、工作目录快照、工具调用和 reasoning 等上下文交给 Python 模板，由模板返回本步骤是否通过。

当前实现位置：

- 基类与通用数据结构：`apps/api/skillhub/application/assertion_base.py`
- Agent 输出与工作目录文件模板：`apps/api/skillhub/application/eval_assertion_templates.py`
- Opencode 过程模板：`apps/api/skillhub/application/opencode_assertion_templates.py`
- Worker 调用入口：`apps/api/skillhub_worker/main.py`
- 单元测试：`apps/api/tests/test_eval_assertion_templates.py`

## 核心模型

每个模板都继承 `AssertionTemplate`，并提供稳定的模板定义和 `evaluate()` 方法。

```python
class MyTemplate(AssertionTemplate):
    id = "my_template"
    name = "用户可见名称"
    description = "用户可见说明"
    category = "分类名称"
    params = (
        AssertionParam("expected", "期望文本", "textarea"),
    )

    def evaluate(self, context: AssertionContext, params: dict[str, Any]) -> AssertionResult:
        ...
```

模板的运行结果必须返回 `AssertionResult`：

```python
AssertionResult(
    passed=True,
    actual="用于展示的实际结果",
    reason="判定说明",
    details={"key": "可选调试信息"},
)
```

## 字段约定

### `id`

`id` 是模板的稳定协议字段，会保存在 `eval_case_versions.steps[].assertion_template_id` 中。

要求：

- 使用小写 snake_case。
- 一旦被测试例使用，不能随意改名。
- 不要复用已有模板 `id`。
- 示例：`agent_output_exact`、`file_created`、`tool_called`。

### `name` / `description` / `category`

这些字段会暴露给前端，用于测试场景编辑器展示。

要求：

- 默认使用中文。
- `name` 简短明确，直接说明判断条件。
- `description` 说明适用场景，而不是重复字段名。
- `category` 用于前端过滤和分组，现有分类包括：
  - `语义判定`
  - `Agent 输出`
  - `工作目录文件`
  - `Opencode 过程`

### `params`

`params` 定义用户需要填写的参数，前端会根据 `params_schema` 动态渲染表单。

```python
AssertionParam(
    name="threshold",
    label="相似度阈值",
    type="number",
    required=True,
    default=0.85,
    placeholder="0 到 1 之间",
    help="越高越严格",
    min=0,
    max=1,
)
```

当前前端稳定支持的 `type`：

- `text`：单行文本。
- `textarea`：多行文本。
- `number`：数字输入。

注意事项：

- 只把用户可配置的字段放进 `params`。
- `normalize_params()` 只会保留模板声明过的参数。
- `required=True` 且参数为空时会直接报错。
- 前端传来的数字可能是字符串，模板内部应显式转换和校验。
- 暂时不要新增复杂参数类型，除非同步补齐前端渲染逻辑。

## `AssertionContext`

`evaluate()` 可以从 `AssertionContext` 读取本步骤运行上下文：

```python
AssertionContext(
    agent_output="Agent 本轮最终文本输出",
    workdir=Path("本步骤工作目录"),
    before_snapshot={"README.md"},
    after_snapshot={"README.md", "result.txt"},
    step={"id": "step-1", ...},
    run_metadata={...},
    reasoning_text="Opencode 捕获到的 reasoning",
    tool_calls=[...],
)
```

常用字段：

- `agent_output`：Agent 本轮最终文本输出，只包含 Opencode `text` parts，不应混入 reasoning。
- `workdir`：本 case 的实际工作目录。
- `before_snapshot`：本步骤执行前的文件快照，元素是相对工作目录的 POSIX 路径。
- `after_snapshot`：本步骤执行后的文件快照。
- `reasoning_text`：Opencode 返回的 reasoning 文本。
- `tool_calls`：标准化后的工具调用列表。

`tool_calls` 当前标准字段：

```python
{
    "tool": "read",
    "status": "completed",
    "input": {"filePath": "README.md"},
    "output_preview": "文件内容预览",
    "call_id": "call_1",
}
```

模板不要直接依赖 Opencode 原始响应结构，应使用 `AssertionContext.tool_calls` 中的标准化字段。

## 结果与异常语义

判断失败和执行异常必须区分清楚。

应该返回 `AssertionResult(False, ...)` 的场景：

- Agent 输出不符合期望。
- 文件不存在。
- 文件内容不匹配。
- 工具调用次数不满足条件。
- reasoning 没有包含指定文本。

应该抛出 `InvariantError` 的场景：

- 模板参数格式不合法。
- 数字阈值超出范围。
- 文件路径存在路径穿越风险。
- 模板无法安全执行。

不要用异常表达普通业务失败。普通业务失败会让该步骤显示为“不通过”；异常会让整个 case run 变成“执行失败”或进入重试。

## 文件路径安全

所有读取工作目录文件的模板都必须使用 `safe_workdir_path()` 解析路径。

```python
path = safe_workdir_path(context.workdir, str(params["path"]))
```

或：

```python
path = safe_workdir_path(
    context.workdir,
    str(params["directory"]),
    str(params["filename"]),
)
```

禁止直接拼接用户输入路径：

```python
# 不要这样写
path = context.workdir / params["path"]
```

`safe_workdir_path()` 会拒绝：

- 绝对路径。
- `..` 路径穿越。
- Windows drive 路径，例如 `C:`.
- 反斜杠路径。
- 空字节。

文件模板还应遵守：

- 不修改工作目录。
- 默认按 UTF-8 读取文本文件。
- `actual` 可以返回文件内容或相对路径，取决于模板展示价值。

## 新增模板步骤

1. 判断模板属于哪个领域。
   - Agent 输出或工作目录文件：优先放在 `eval_assertion_templates.py`。
   - Opencode 工具调用或 reasoning：放在 `opencode_assertion_templates.py`。
   - 如果同类模板明显增多，再拆新的领域模块，避免单文件膨胀。

2. 新增一个继承 `AssertionTemplate` 的类。

3. 定义 `id/name/description/category/params`。

4. 实现 `evaluate()`。

5. 注册模板。
   - 通用模板加入 `TEMPLATES`。
   - Opencode 过程模板加入 `opencode_process_templates()` 返回值。

6. 添加单元测试。

7. 运行验证。

```bash
cd apps/api
uv run pytest tests/test_eval_assertion_templates.py
```

如果改动影响前端展示，再运行：

```bash
cd apps/web
npm run lint
npm run build
```

## 示例：Agent 输出包含文本

```python
class AgentOutputContainsTemplate(AssertionTemplate):
    id = "agent_output_contains"
    name = "Agent 输出包含文本"
    description = "Agent 本轮输出必须包含指定文本。"
    category = "Agent 输出"
    params = (
        AssertionParam("text", "必须包含", "textarea", placeholder="填写必须出现的关键文本"),
    )

    def evaluate(self, context: AssertionContext, params: dict[str, Any]) -> AssertionResult:
        needle = str(params["text"])
        passed = needle in context.agent_output
        return AssertionResult(
            passed,
            context.agent_output,
            "输出包含指定文本。" if passed else "输出未包含指定文本。",
            {"text": needle},
        )
```

## 示例：文件内容包含文本

```python
class FileContentContainsTemplate(AssertionTemplate):
    id = "file_content_contains"
    name = "路径下文件内容包含文本"
    description = "指定文件必须存在，且内容包含指定文本。"
    category = "工作目录文件"
    params = (
        AssertionParam("path", "文件路径", "text", placeholder="例如：docs/output.md"),
        AssertionParam("text", "必须包含", "textarea"),
    )

    def evaluate(self, context: AssertionContext, params: dict[str, Any]) -> AssertionResult:
        path = safe_workdir_path(context.workdir, str(params["path"]))
        if not path.is_file():
            return AssertionResult(False, "", "文件不存在。", {"path": str(params["path"])})
        actual = path.read_text(encoding="utf-8")
        needle = str(params["text"])
        passed = needle in actual
        return AssertionResult(
            passed,
            actual,
            "文件内容包含指定文本。" if passed else "文件内容未包含指定文本。",
            {"path": str(params["path"]), "text": needle},
        )
```

## 示例：工具调用次数

过程类模板应使用 `context.tool_calls`：

```python
class ToolCalledTemplate(AssertionTemplate):
    id = "tool_called"
    name = "调用过指定工具"
    description = "检查本步骤是否至少调用过指定 Opencode 工具。"
    category = "Opencode 过程"
    params = (
        AssertionParam("tool", "工具名", "text", placeholder="例如：read"),
    )

    def evaluate(self, context: AssertionContext, params: dict[str, Any]) -> AssertionResult:
        tool = str(params["tool"]).strip()
        if not tool:
            raise InvariantError("Tool name is required.")
        calls = [call for call in context.tool_calls if str(call.get("tool") or "") == tool]
        passed = len(calls) > 0
        return AssertionResult(
            passed,
            "\n".join(str(call) for call in context.tool_calls),
            "已调用指定工具。" if passed else "未调用指定工具。",
            {"tool": tool, "count": len(calls)},
        )
```

## 测试建议

每个新模板至少覆盖：

- 通过场景。
- 不通过场景。
- 必填参数缺失或格式非法。
- 如果涉及路径，覆盖路径穿越和 Windows 风格不安全路径。
- 如果涉及数字，覆盖边界值和非法值。
- 如果涉及 Opencode 过程，覆盖空 `tool_calls` 或空 `reasoning_text`。

测试应优先直接调用模板：

```python
template = assertion_template("your_template_id")
result = template.evaluate(context(tmp_path, output="..."), {"param": "value"})
assert result.passed is True
```

## 发布前检查清单

- `id` 稳定且未冲突。
- 用户可见文案是中文。
- 参数 schema 只包含前端已支持的类型。
- 普通不通过返回 `AssertionResult(False, ...)`。
- 参数非法或路径不安全才抛 `InvariantError`。
- 文件访问使用 `safe_workdir_path()`。
- 模板已注册到 registry。
- 单元测试覆盖通过、不通过和异常场景。
- `GET /api/eval-assertion-templates` 能返回新模板定义。
