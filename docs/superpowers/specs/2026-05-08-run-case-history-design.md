# SkillHub Run 与 Case History 设计规格

日期：2026-05-08

状态：待用户审阅后进入实现计划

## 1. 背景

当前正式版已经完成一条可运行主链路：

- 标准 skill folder / zip 导入。
- skill、variant、variant version、eval case、manual eval run 的基础操作。
- `EvalRun = exact VariantVersion + EvalSetVersion` 的数据绑定。
- `EvalSetVersion = case version snapshot` 的不可变测试集语义。
- `skill_bundle` 文件树预览和版本 diff。
- `/skills` 三栏工作台、视觉回归、README 一键启动说明。

但维护者做多轮实验后仍然缺两个关键视角：

1. 以前测过什么，结果如何，绑定的是哪一版 skill 和哪一版测试集。
2. 一个测试用例被编辑过几次，每一版输入、期望输出和 notes 是什么，被哪些 eval set version 使用过。

这两个视角是“测评驱动 skill 迭代”的基础证据链。没有它们，用户只能看到最近一次结果，无法审查回归、解释历史分数，也无法判断测试集质量是否稳步变好。

## 2. 外部实践调研

### GitHub Actions Run History

GitHub Actions 把历史运行作为一等列表入口：用户先看到 workflow run list，再点进单次 run 查看 jobs、logs、status 和触发信息。

适配 SkillHub：

- Eval run history 应该先是一个可过滤列表，而不是只在 skill summary 里显示 latest run。
- 列表必须直接显示 status、strategy、绑定版本、通过率和创建时间。
- 单 run 详情继续复用现有 `/eval-runs/:runId`，第一版不重做完整详情页。

参考：https://docs.github.com/en/actions/how-tos/monitor-workflows/view-workflow-run-history

### LangSmith Experiment Analysis

LangSmith 的 experiment 结果视图强调表格、列配置、排序过滤、compact/full/diff 视图、baseline 对比和回归定位。

适配 SkillHub：

- 第一版先做表格和轻量筛选，不做复杂 matrix 或 baseline compare。
- 后续可以把 run history 扩展为 eval matrix：行是 case，列是 variant version / run。
- 运行历史必须保留 exact binding，否则比较没有意义。

参考：https://docs.langchain.com/langsmith/analyze-an-experiment

### Linear Filters

Linear 的核心操作体验是：列表视图顶部提供低摩擦过滤，用户不离开上下文即可缩小范围。

适配 SkillHub：

- History tab 顶部使用 compact filter bar。
- 第一版只做枚举筛选：variant version、eval set version、strategy、status。
- 不做 query builder、saved view、复杂搜索语法。

参考：https://linear.app/docs/filters

### Sentry Issue Details

Sentry 的详情页把事件、tags、上下文、时间线和相关证据聚合在一个 triage surface 中，让用户快速判断问题演化。

适配 SkillHub：

- Case version history 应该以内联 timeline 方式出现在 case 上下文里，而不是另开复杂管理页面。
- 每个 case version 要显示当时的 input、expected output、notes、创建人、创建时间和所属 eval set snapshots。
- 只读历史优先于“恢复到旧版”等写操作；恢复/rollback 留到后续。

参考：https://docs.sentry.io/product/issues/issue-details/

## 3. 目标

本阶段让维护者能回答四个问题：

1. 这个 skill 最近做过哪些测评？
2. 每次测评绑定的是哪个 `VariantVersion` 和哪个 `EvalSetVersion`？
3. 哪些 run 失败了，失败的是哪些 case？
4. 某个 case 的历史版本是什么，测试集版本什么时候引用过这些 case version？

完成后，`/skills` 工作台应该能从“当前状态面板”升级为“可追溯实验台”：用户既能新增/执行，也能回看证据。

## 4. 非目标

第一版不做：

- run-to-run 差异比较。
- baseline / regression matrix。
- saved filters 或自定义视图。
- case version rollback / restore。
- 批量导出 CSV。
- 自动评估策略执行器。
- 权限角色和审计日志 UI。

这些都依赖 history read model，但不应该塞进第一版。

## 5. 推荐方案

### 方案 A：只用现有 `skill.latest_eval_runs` 和 detail 页面

做法：

- 不加后端 endpoint。
- 前端从 `GET /api/skills/{skill_id}` 的 `latest_eval_runs` 展示最近几次。
- case history 暂不做。

优点：

- 最快，几乎没有后端改动。

缺点：

- 不支持筛选。
- 只能看少量 latest，不是真正 history。
- case version history 仍然缺失。
- 后续做 matrix 时还要推翻。

### 方案 B：新增两个只读 read model，前端渲染 History tab

做法：

- 新增 `GET /api/skills/{skill_id}/eval-runs`。
- 新增 `GET /api/eval-cases/{case_id}/versions`。
- `/skills` 增加 `历史` tab，展示 run history 表和 selected run 的 case results。
- 在 eval case 卡片上增加 `版本历史` 入口，展示 case version timeline。

优点：

- 契合当前架构：命令写入，read model 查询。
- 不改变核心数据模型。
- 支持后续 compare、matrix、promotion review。
- 对用户有直接价值：能查历史、能解释 case 演化。

缺点：

- 需要新增 API、类型、UI、E2E。
- 现有 `decision-workbench.tsx` 已偏大，本次实现需要顺手抽取一部分 history 组件，避免继续腐化。

### 方案 C：直接做完整实验矩阵

做法：

- 一步做 run history、case history、run compare、variant matrix、baseline、回归标记。

优点：

- 最终形态更强。

缺点：

- 范围过大，交互和数据契约容易失控。
- 当前用户最缺的是回看历史，不是高级分析。
- 会破坏“步步为营”的产品节奏。

### 推荐

采用方案 B。

这是当前成熟化路径上最小但完整的一步：补齐历史证据链，不引入大矩阵复杂度。后端 read model 保持明确；前端只在现有三栏工作台中增加一个 History tab，符合 Linear/GitHub 的轻量列表入口，也不打断现有 import / eval / diff 流。

## 6. 数据契约

### 6.1 Eval Run History

新增 endpoint：

```text
GET /api/skills/{skill_id}/eval-runs
```

Query 参数：

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `variant_version_id` | string | 可选，只看某个 VariantVersion 的 runs |
| `eval_set_version_id` | string | 可选，只看某个 EvalSetVersion 的 runs |
| `strategy` | string | 可选，例如 `manual_pass_fail` |
| `status` | string | 可选，例如 `finished` |
| `limit` | int | 可选，默认 50，最大 200 |

返回：

```json
{
  "skill": {
    "id": "skill_code_reviewer",
    "slug": "code-reviewer"
  },
  "runs": [
    {
      "eval_run": {
        "id": "run_123",
        "skill_id": "skill_code_reviewer",
        "variant_version_id": "version_a_v2",
        "eval_set_version_id": "evalset_v3",
        "strategy": "manual_pass_fail",
        "status": "finished",
        "summary": { "passed": 4, "failed": 1, "total": 5 },
        "created_at": "2026-05-08T10:00:00Z",
        "created_by": "product-operator"
      },
      "variant": {
        "id": "variant_a",
        "label": "Imported",
        "tags": ["codex", "gpt5.4"]
      },
      "variant_version": {
        "id": "version_a_v2",
        "version_number": 2,
        "change_summary": "Add tenant filter guidance"
      },
      "eval_set": {
        "id": "evalset_primary",
        "name": "Primary"
      },
      "eval_set_version": {
        "id": "evalset_v3",
        "version_number": 3
      }
    }
  ]
}
```

约束：

- 只能返回同一 skill 的 runs。
- 默认按 `created_at desc` 排序。
- `limit` 超过 200 时截断到 200。
- 第一版不分页；当数据规模需要时再加 cursor。

### 6.2 Case Version History

新增 endpoint：

```text
GET /api/eval-cases/{case_id}/versions
```

返回：

```json
{
  "case": {
    "id": "case_missing_owner",
    "skill_id": "skill_code_reviewer",
    "title": "PR: missing owner filter",
    "current_version_id": "casever_2",
    "lifecycle_status": "active"
  },
  "versions": [
    {
      "case_version": {
        "id": "casever_2",
        "version_number": 2,
        "notes": "Clarify expected tenant-scope finding.",
        "created_at": "2026-05-08T10:00:00Z",
        "created_by": "product-operator",
        "input_artifact": {
          "id": "artifact_input_2",
          "digest": "sha256:...",
          "content_text": "diff --git ..."
        },
        "expected_output_artifact": {
          "id": "artifact_expected_2",
          "digest": "sha256:...",
          "content_text": "Must flag missing tenant scope."
        }
      },
      "included_in_eval_set_versions": [
        {
          "id": "evalset_v3",
          "eval_set_id": "evalset_primary",
          "version_number": 3,
          "position": 0
        }
      ]
    }
  ]
}
```

约束：

- 按 `version_number desc` 返回。
- artifact 内容沿用现有文本 artifact 行为；大文件/二进制后续再做 lazy artifact read。
- archived case 仍然可以按 id 读取历史。

## 7. UI 设计

### 7.1 `/skills` 新增 History tab

在现有 mode 中加入：

```ts
type Mode = "overview" | "variants" | "evals" | "diff" | "history";
```

History tab 结构：

```text
Toolbar
  title: 历史记录
  subtitle: N runs · M case versions
  filters: variant version / eval set version / strategy / status

Main
  left/table: run rows
    pass rate
    variant version
    eval set version
    strategy
    status
    created time
    actor

  right/detail panel:
    selected run binding
    pass/fail summary
    case result rows
    link: 打开 EvalRun 详情
```

交互原则：

- 默认选中最新 run。
- 空状态显示：`还没有测评历史。先在“测评”里记录一次 run。`
- filter 改变后保留当前选中 run；如果不在结果中，选中第一条。
- 表格行点击只更新详情，不跳页。
- 详情里保留 `/eval-runs/{id}` 链接，满足深度查看。

### 7.2 Case Version History 入口

在 Evals tab 的 case card footer 增加 `历史` 按钮。

点击后：

- 保持在 Evals tab。
- 右侧 detail 区切换到该 case 的 version timeline。
- timeline 展示每个 case version 的 version number、notes、created_by、created_at、input、expected output。
- 每个 version 下方显示被哪些 eval set version 引用。

第一版不做 restore，只读。

### 7.3 Inspector 调整

右侧 inspector 不新增大表单。

- History tab 时 inspector 显示 selected run 的 verification card 和快捷操作：
  - 打开 EvalRun 详情。
  - 切换到测评继续记录。
  - 切换到差异比较。
- Case history 展开时 inspector 保持原有 case 编辑入口。

## 8. 状态与错误处理

| 场景 | UI 行为 |
| --- | --- |
| 没有 eval runs | History tab 显示空状态和 `去记录测评` 按钮 |
| filter 无结果 | 显示空结果，但保留 filter bar |
| selected run 被筛掉 | 自动选中结果第一条 |
| run detail 加载失败 | 行仍显示，详情区显示错误和重试 |
| case 没有多个版本 | timeline 显示当前唯一版本 |
| case 已归档 | history 可读，编辑/记录按钮禁用或保留归档状态 |
| API 返回跨 skill 数据 | 后端拒绝，前端显示错误 |

## 9. 实现边界

后端：

- `SqlSkillRepository.list_eval_runs_for_skill(...)`
- `SqlSkillRepository.eval_case_history(case_id)`
- FastAPI routes。
- API tests 覆盖 filters、ordering、same-skill scoping、archived case readability。

前端：

- 新增 types：`EvalRunHistory`, `EvalRunHistoryRow`, `EvalCaseHistory`。
- `decision-workbench.tsx` 增加 history mode，但把大块 UI 抽出到局部组件或新组件文件，避免文件继续膨胀。
- Evals pane 增加 case history selection。
- Playwright 覆盖：
  - 连续记录两次 run 后，History tab 显示两行并可筛选。
  - 编辑 case 后，点击历史能看到 v1/v2 的 input/expected 内容。

文档：

- README 增加 History tab 使用说明。
- `docs/product-ux-review.md` 将 run history / case history 从 missing 移到 working flow，并新增下一轮 friction。
- `docs/product-completion-audit-2026-05-08.md` 更新证据表。

## 10. 测试计划

### 后端

新增 API command tests：

1. `test_eval_run_history_filters_by_variant_eval_set_strategy_status`
2. `test_eval_run_history_orders_newest_first_and_limits_results`
3. `test_eval_case_history_returns_versions_and_eval_set_membership`
4. `test_eval_case_history_reads_archived_case`

运行：

```bash
cd apps/api
uv run pytest tests/test_api_commands.py -k "history or eval_run_history" -v
uv run pytest
```

### 前端

新增 E2E：

1. `operator can review eval run history with filters`
2. `operator can inspect eval case version history`

运行：

```bash
cd apps/web
npm run typecheck
npm run build
npm run e2e -- --grep "history"
npm run e2e
```

### 全量门禁

提交前必须通过：

```bash
cd apps/api && uv run pytest
cd apps/web && npm run typecheck
cd apps/web && npm run build
cd apps/web && npm run e2e
git diff --check
```

## 11. 成功标准

1. 用户能在 `/skills` 打开 `历史` tab。
2. 用户能看到当前 skill 的多次 eval run，并知道每次绑定的 variant version 和 eval set version。
3. 用户能按 variant version、eval set version、strategy、status 过滤 run history。
4. 用户能点击一条 run，在同页看到 case-level pass/fail。
5. 用户能从某个 case 看到 v1/v2 等历史版本的 input、expected output、notes。
6. 用户能看到每个 case version 被哪些 eval set version 引用。
7. 后端 read model 不改变写模型，不破坏 exact version binding。
8. README 和产品审计文档更新。
9. 全量验证通过后再推送。

## 12. 自检

- Placeholder scan：没有占位标记，没有空章节。
- Scope check：只做 history read model 和 UI，不做 compare/matrix/rollback/export。
- Consistency check：新增 endpoint 都是只读；写操作仍走现有 command endpoints。
- Ambiguity check：filter、排序、limit、空状态、archived case 可读性都已明确。
