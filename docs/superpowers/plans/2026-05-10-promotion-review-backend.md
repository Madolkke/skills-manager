# Promotion Review Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现“设为当前版本评审”的后端 read model、promotion command、结构化决策记录和审计记录。

**Architecture:** 在 `SqlSkillRepository` 内新增 promotion review 读模型和带证据的 promotion command，API 路由只做 payload 解析与方法调用。复用现有 `VariantVersion`、`EvalSetVersion`、`EvalRun`、`case_results`、`bundle_diff` 能力，新增 `promotion_decisions` 表作为可查询的结构化历史。

**Tech Stack:** FastAPI、Pydantic、SQLAlchemy Core、SQLite/PostgreSQL-compatible metadata、pytest/unittest。

---

### Task 1: 写失败测试覆盖后端契约

**Files:**
- Modify: `apps/api/tests/test_sqlalchemy_metadata.py`
- Modify: `apps/api/tests/test_sql_repository.py`
- Modify: `apps/api/tests/test_api_commands.py`

- [ ] **Step 1: 写 metadata 测试**

覆盖新增 `promotion_decisions` 表、索引和关键外键，确保 SQLite test schema 与正式 schema 同步。

- [ ] **Step 2: 写 repository read model 测试**

覆盖：

- ready：候选版本完整测评、无回退，逐 case 统计包含 `fixed`、`stable_pass`。
- risky：候选版本造成回退，`requires_note = true`。
- unverified：候选版本没有测评。

- [ ] **Step 3: 写 repository command 测试**

覆盖：

- 证据 run 不属于候选版本时拒绝。
- 有风险但缺少理由时拒绝。
- 成功后移动 `current_version_id`，写入 `promotion_decisions` 和 `audit_events`。

- [ ] **Step 4: 写 API 测试**

覆盖：

- `GET /api/variants/{variant_id}/promotion-review`
- `POST /api/variants/promotions`

- [ ] **Step 5: 运行失败测试**

Run:

```bash
cd apps/api && UV_CACHE_DIR=/Users/xx/Documents/code/skills-manager/.uv-cache uv run pytest tests/test_sqlalchemy_metadata.py tests/test_sql_repository.py tests/test_api_commands.py -q
```

Expected: FAIL，缺失 `promotion_decisions`、`promotion_review` 或新 payload 字段。

### Task 2: 实现 schema 与 metadata

**Files:**
- Modify: `apps/api/skillhub/infrastructure/db/tables.py`
- Modify: `apps/api/skillhub/infrastructure/db/schema.sql`
- Modify: `apps/api/migrations/versions/0001_initial_schema.py`

- [ ] **Step 1: 新增 `promotion_decisions` metadata 表**

字段：

- `id`
- `skill_id`
- `variant_id`
- `from_version_id`
- `to_version_id`
- `eval_set_version_id`
- `evidence_eval_run_id`
- `baseline_eval_run_id`
- `readiness_status`
- `summary`
- `decision_note`
- `created_at`
- `created_by`

- [ ] **Step 2: 新增正式 SQL DDL**

保持 PostgreSQL `jsonb`，并补充查询索引。

- [ ] **Step 3: 更新 downgrade 顺序**

在 `audit_events` 后、`role_assignments` 前 drop `promotion_decisions`。

- [ ] **Step 4: 跑 metadata 测试**

Run:

```bash
cd apps/api && UV_CACHE_DIR=/Users/xx/Documents/code/skills-manager/.uv-cache uv run pytest tests/test_sqlalchemy_metadata.py -q
```

Expected: PASS。

### Task 3: 实现 repository read model

**Files:**
- Modify: `apps/api/skillhub/infrastructure/db/repositories.py`

- [ ] **Step 1: 新增 `promotion_review(...)`**

参数：

- `variant_id`
- `candidate_version_id`
- `eval_set_version_id | None`

返回 dict，包含 skill、variant、current_version、candidate_version、eval_set、eval_set_version、candidate_run、current_run、readiness、comparison_summary、case_comparisons、bundle_diff。

- [ ] **Step 2: 复用 helper**

新增私有 helper：

- `_latest_finished_run(...)`
- `_case_results_by_case_version(...)`
- `_promotion_case_comparisons(...)`
- `_promotion_readiness(...)`

- [ ] **Step 3: 跑 read model 测试**

Run:

```bash
cd apps/api && UV_CACHE_DIR=/Users/xx/Documents/code/skills-manager/.uv-cache uv run pytest tests/test_sql_repository.py -k promotion_review -q
```

Expected: PASS。

### Task 4: 实现带证据的 promotion command

**Files:**
- Modify: `apps/api/skillhub/infrastructure/db/repositories.py`

- [ ] **Step 1: 扩展 `promote_variant_version(...)`**

新增参数：

- `evidence_eval_run_id`
- `eval_set_version_id`
- `decision_note`
- `accept_risk`
- `actor`

先校验 variant/version 归属，再校验证据 run 绑定候选版本和测试集版本。

- [ ] **Step 2: 用 read model 判断风险**

如果 `readiness.status` 为 `unverified` 或 `blocked`，拒绝。

如果 `readiness.requires_note` 为 true：

- `decision_note` 必须非空。
- `accept_risk` 必须为 true。

- [ ] **Step 3: 写入决策和审计**

成功后：

- 更新 `variants.current_version_id`。
- 插入 `promotion_decisions`。
- 插入 `audit_events`，payload 包含 `promotion_decision_id`。

- [ ] **Step 4: 跑 command 测试**

Run:

```bash
cd apps/api && UV_CACHE_DIR=/Users/xx/Documents/code/skills-manager/.uv-cache uv run pytest tests/test_sql_repository.py -k promote -q
```

Expected: PASS。

### Task 5: 接 API 路由与 payload

**Files:**
- Modify: `apps/api/skillhub/api/main.py`
- Modify: `apps/api/tests/test_api_commands.py`

- [ ] **Step 1: 新增 read endpoint**

```text
GET /api/variants/{variant_id}/promotion-review
```

- [ ] **Step 2: 扩展 command payload**

`POST /api/variants/promotions` 接收证据 run、测试集版本、理由、风险确认和操作者。

- [ ] **Step 3: 跑 API 测试**

Run:

```bash
cd apps/api && UV_CACHE_DIR=/Users/xx/Documents/code/skills-manager/.uv-cache uv run pytest tests/test_api_commands.py -k promotion -q
```

Expected: PASS。

### Task 6: 回归与任务状态

**Files:**
- Modify: `.agent/tasks.json`

- [ ] **Step 1: 跑全量后端测试**

Run:

```bash
cd apps/api && UV_CACHE_DIR=/Users/xx/Documents/code/skills-manager/.uv-cache uv run pytest
```

Expected: PASS。

- [ ] **Step 2: 标记 TASK-001 通过**

把 `.agent/tasks.json` 中 `001` 的 `passes` 改为 `true`。

- [ ] **Step 3: 提交**

```bash
git add apps/api .agent/tasks.json docs/superpowers/plans/2026-05-10-promotion-review-backend.md
git commit -m "feat: add promotion review backend"
```

## 自审

- 覆盖 `.agent/tasks/TASK-001.json` 的所有后端要求。
- 不改前端 UI；前端会在下一任务接入新契约。
- 不把业务规则写在 FastAPI 路由里。
- 新表同时更新 SQLAlchemy metadata 和正式 SQL schema。
