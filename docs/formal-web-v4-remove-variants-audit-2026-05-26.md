# SkillHub 去 Variant 化正式收口审计（2026-05-26）

## 结论

本轮正式收口把旧 `Variant / VariantVersion` 模型直接移除，当前产品和核心 API 统一为：

```text
Skill -> SkillVersion -> EvalRun(environment_tags, run_context) + EvalSetVersion
```

运行环境标签不再描述内容版本，而是作为一次测评运行的事实写入 `EvalRun`。这样同一个 `SkillVersion` 可以在 Windows、CI、本地 runner、不同 model 或不同 sandbox 下留下多组独立证据，历史页和 accepted verification 也能按运行上下文区分。

## 为什么移除 Variant

- 旧模型把“内容版本”和“运行环境约束”绑在同一个对象上，导致相同 Skill 在不同环境运行时需要人为创建额外分组。
- 用户实际关心的是某个不可变 bundle 在某个测评集和某个运行环境下的结果，而不是先理解一层人工分组。
- Tag 的语义更接近运行事实：`windows`、`codex`、`gpt-5`、`ci` 这些值会随每次 run 改变，不应决定内容版本身份。
- 直接使用 `SkillVersion` 后，版本线、Bundle diff、历史证据和手工测评入口更短，数据链路也更容易验收。

## 字段迁移

| 旧语义 | 新语义 |
| --- | --- |
| 内容快照 | `skill_versions` |
| 当前内容指针 | `skills.current_version_id` |
| 运行环境 tags | `eval_runs.environment_tags` |
| 结构化运行上下文 | `eval_runs.run_context` |
| 上下文唯一键 | `eval_runs.run_context_hash` |
| 验证指针上下文 | `(skill_id, skill_version_id, eval_set_version_id, run_context_hash)` |
| Bundle diff 参数 | `left_skill_version_id` / `right_skill_version_id` |

## 数据库与迁移行为

- fresh schema 不再创建旧内容分组表。
- 在线 migration 创建 `skill_versions`，把旧内容快照复制过去，并按 Skill 内创建顺序重新分配 `version_number`。
- `skills.current_version_id` 指向迁移后的当前 `SkillVersion`。
- 历史 `eval_runs` 改为引用 `skill_version_id`。
- 旧运行约束标签迁入 `eval_runs.environment_tags`。
- 所有历史 run 计算 `run_context_hash`，accepted verification 按 run context 重新建立唯一约束。
- Windows Git Bash 默认启动使用 Python 侧生成的文件型 SQLite URL，避免落到 `sqlite:///:memory:`。

## API 与 UI 收口

- `POST /api/skill-imports` 只接收 `owner_ref + source`，不再要求 tag。
- `POST /api/skill-versions` 追加不可变版本，并可用 `make_current` 移动当前指针。
- `POST /api/eval-runs` 接收 `skill_version_id`、`eval_set_version_id`、`environment_tags`、`run_context` 和逐 case `{ passed, actual_output }`。
- `GET /api/artifacts/diff` 使用 `left_skill_version_id` 和 `right_skill_version_id`。
- Web V4 tab 从 `变体` 改为 `版本`。
- 新建 Skill 表单移除 tags。
- 手工测评页加入运行环境标签、OS、Runner、Model 输入。
- 历史页展示 `SkillVersion`、`EvalSetVersion`、运行环境、actual vs expected 和 artifact digest。
- 小窗口 responsive smoke 覆盖 Hub、概览、测评集、测评、历史和版本页。

## 验证记录

本轮最终验证：

```bash
cd apps/api && uv run pytest tests/test_schema_contract.py tests/test_sqlalchemy_metadata.py -q
# 17 passed

cd apps/api && uv run pytest -q
# 55 passed

cd apps/api && uv run python -m compileall skillhub tests
# passed

cd apps/web-v4 && npm run test
# 9 passed

cd apps/web-v4 && npm run lint
# passed

cd apps/web-v4 && npm run build
# passed

cd apps/web-v4 && npm run e2e
# 2 passed

cd apps/web-v4 && npm run e2e:visual
# 1 passed

git diff --check
# passed
```

工具链备注：

- Web lint 使用项目内 `npm run lint`，已通过。
- API 当前没有配置 Python lint target，CI 也只运行 API pytest；临时 `uvx ruff check .` 在本机等待工具解析时无输出并被终止，因此本轮额外跑了 `compileall` 做语法完整性检查。后续如需强制 API lint，应把 ruff 明确加入 `apps/api/pyproject.toml` 的 dev 依赖和 CI。

agent-browser 实操确认：

- `/skills` 能加载。
- 通过 API seed 了一个 Skill 和两个 `SkillVersion`，浏览器打开 `/skills?skill=<id>&tab=versions` 后 `版本` tab 可见。
- Bundle diff 面板显示后端真实数据：`v2 对比 v1`，包含 `SKILL.md` 和 `references/checklist.md` 的 hunk。
- 在测评页输入 `codex`、`windows`、`os=windows`、`runner=local`、`model=gpt-5` 和 actual output，并通过 UI 记录 EvalRun。
- 历史页显示 `SkillVersion v2`、`EvalSetVersion Primary v2`、运行环境、actual output 与 expected output。
- 用同一个 `SKILLHUB_DATA_DIR=/private/tmp/skillhub-devariant-smoke-data` 重启服务后，历史页仍显示同一 run。
- `agent-browser set viewport 320 820` 后，历史页 `documentElement.scrollWidth=320`、`body.scrollWidth=320`、`overflow=false`。

## 剩余风险

- 历史设计文档仍可能保留旧模型讨论；这些文档只作为历史背景，不作为当前契约来源。
- 当前本地 actor 机制仍是开发期能力，正式认证仍需后续任务接入真实 session 或 token。
- Worker 和外部自动策略尚未作为正式执行链路接入；当前正式闭环以手工测评和可导入事实为准。
