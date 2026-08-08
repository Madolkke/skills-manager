# Workflow 采集与表达式系统测试审计报告

**日期**：2026-08-09
**范围**：CLI、Log、Config Collection，`inputs`/`outputs`/`config` 表达式，多采样索引，批量校验及 executor 投影。
**方法**：后端、前端和跨层 Agent 独立运行定向测试并审阅实现，主 Agent 汇总后补充回归测试。

## Agent 结论

### 后端 Agent

- 采集联合模型、v4/v5 迁移、Workflow validation、Config DSL、Log SQL 和 executor 投影基线通过。
- 发现 Log SQL 对 SQLGlot `Anonymous` 函数只检查 `sql_name()`，导致 `load_extension`、`read_csv_auto`、`http_get`、`glob` 等投影函数绕过外部来源门禁。
- 发现多采样输出切片后直接访问字段没有诊断，类型推导退化为 `any`。

### 前端 Agent

- 发现多采样表达式补全未校验下标类型，字符串、浮点、布尔及嵌套未闭合下标仍可能给出字段补全。
- 发现 Config 递归编辑器使用数组路径作为 Vue key，排序或删除时可能复用错误的局部状态。
- 发现 Config 错误定位只按命令名称和字段后缀匹配，同名递归节点可能误标。
- 发现批量校验任一步失败时会清空所有诊断，且缺少多 Step 部分失败、卸载和 stale response 测试。

### 跨层 Agent

- 确认 Config 非法字符串/数组下标在后端是同步阻断错误，但前端此前只展示为诊断，未纳入同步门禁。
- 确认前后端重复 call key 的环境投影策略缺少明确回归契约。
- 确认 Log/Config 过滤、Step 作用域和 executor 投影需要同一 fixture 的深度比较。

## 已修复问题

| 优先级 | 问题 | 修复与证明 |
| --- | --- | --- |
| P1 | Log SQL 匿名函数绕过外部来源限制 | 按 `exp.Anonymous.name` 检查真实函数名，并补充扩展加载、文件读取、网络和 shell 函数测试。 |
| P2 | 多采样切片后直接字段访问无诊断 | 对切片数组属性访问产生 `SAMPLE_INDEX_REQUIRED`，保留合法切片结果类型。 |
| P2 | 非法多采样下标仍触发前端补全 | 仅允许整数、负整数和标识符路径索引；阻断字符串、浮点、布尔、切片和未闭合嵌套下标。 |
| P2 | Config 非法下标未进入同步门禁 | 前端将 `CONFIG_STRING_SUBSCRIPT_FORBIDDEN` 和 `CONFIG_ARRAY_INDEX_INVALID` 映射为 error。 |
| P2 | 单个 Step 批量校验失败清空全部诊断 | 改用 `Promise.allSettled`，成功批次独立刷新，失败批次保留未变更表达式的旧结果。 |
| P2 | Config 递归节点身份和错误定位不稳定 | 使用前端内存稳定 key，并按完整 `spec.config.commands[...]` 路径定位错误。 |
| P2 | 无效草稿重复 call key 的环境投影前后端策略不一致 | 后端与前端统一为同一 Step 内 first-wins，并补充跨层回归测试。 |

## 测试证据

- 后端定向采集、表达式、规则、迁移、生成器、executor 和 API 测试通过。
- 后端完整测试：`338 passed, 181 skipped`。
- 前端完整测试：`29` 个测试文件、`201` 项通过。
- 前端 `vue-tsc` 和 ESLint 通过。
- API 批量表达式验证覆盖请求顺序、重复 ID 和 1000 条上限。
- executor projection 覆盖 CLI/Log/Config 混合调用，确认被过滤调用不占 ID 且引用文本不被改写。

## 残余风险与后续测试

- `outputs.<call>[start:end].field` 已阻断，但切片后的元素访问语法仍需在文档中明确是否支持。
- 公共 `workflow_expression_environment()` 的跨 Step 同名 call key 仍属于兼容投影；生产 Workflow validation 使用 Step-scoped 环境，已补充同 Step 重复 key 的 first-wins 回归。
- Log 列目录请求失败仍使用 fallback，建议增加 loading/error 状态和 UI 提示。
- Config 递归编辑器需要 Playwright 视觉回归，覆盖 1440、1280、1180、1024、768、375 宽度。
- 全仓库 mypy 存在既有 mixin 类型错误，未归因于本次修改；变更模块以 `vue-tsc`、Ruff 和定向检查为准。

## 验收命令

```text
uv run python -m compileall -q skillhub skillhub_worker
uv run ruff check skillhub skillhub_worker tests
uv run pytest -q
uv run pytest -q tests/test_architecture_layers.py
npm run test
npm run lint
npx vue-tsc --noEmit -p tsconfig.app.json
npm run build
```

历史审计报告 `docs/workflow-code-audit-2026-08-01.md` 未修改。
