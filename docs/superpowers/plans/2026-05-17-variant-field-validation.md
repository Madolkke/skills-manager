# Variant Field Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 variant 和 variant version 高频写入字段增加后端长度上限，并让主工作区表单展示字段级错误。

**Architecture:** 后端在 FastAPI payload 类型层增加 `Field(max_length=...)`，继续走现有 request validation -> `field_errors` 转换。前端把主工作区两个 raw form 改为共享 `ValidatedForm` 和 `WorkbenchField`，并让 mutation handler 对 API 字段错误 rethrow。

**Tech Stack:** FastAPI、Pydantic、pytest、React、Next.js、Playwright。

---

### Task 1: API 字段长度红绿测试

**Files:**
- Modify: `apps/api/tests/test_api_commands.py`
- Modify: `apps/api/skillhub/api/main.py`

- [x] **Step 1: 写失败测试**
  - 新增 `test_variant_write_fields_return_field_errors`。
  - 创建 skill 后，分别验证：
    - `POST /api/variants` 的 `label` 超过 80 字符返回 `field_errors[0].field == "label"`。
    - `POST /api/variants` 的 `summary` 超过 1000 字符返回 `field_errors[0].field == "summary"`。
    - `POST /api/variant-versions` 的 `change_summary` 超过 1000 字符返回 `field_errors[0].field == "change_summary"`。

- [x] **Step 2: 跑红灯**
  - Run: `cd apps/api && UV_NO_CACHE=1 uv run pytest tests/test_api_commands.py -k "variant_write_fields"`
  - Expected: FAIL，因为这些字段还没有长度上限。

- [x] **Step 3: 加后端类型上限和中文错误**
  - 在 `apps/api/skillhub/api/main.py` 增加：
    - `VARIANT_LABEL_MAX_LENGTH = 80`
    - `VARIANT_SUMMARY_MAX_LENGTH = 1000`
    - `VERSION_CHANGE_SUMMARY_MAX_LENGTH = 1000`
  - 定义 `VariantLabel`、`VariantSummary`、`VersionChangeSummary`。
  - 应用到 `CreateSkillPayload`、`ImportSkillPayload`、`CreateVariantPayload` 和 `CreateVariantVersionPayload`。
  - `request_validation_message` 对 `variant_label`、`label`、`variant_summary`、`summary`、`change_summary` 的 `string_too_long` 返回中文上限。

- [x] **Step 4: 跑 API 绿灯**
  - Run: `cd apps/api && UV_NO_CACHE=1 uv run pytest tests/test_api_commands.py -k "variant_write_fields"`
  - Expected: PASS。

### Task 2: 主工作区表单字段错误

**Files:**
- Modify: `apps/web/components/variants/variant-creation-composer.tsx`
- Modify: `apps/web/components/variants/workspace-version-composer.tsx`
- Modify: `apps/web/components/decision-workbench.tsx`
- Modify: `apps/web/e2e/form-errors.spec.ts`

- [x] **Step 1: 写 E2E 红测**
  - 在 `form-errors.spec.ts` 新增测试：
    - 导入 skill。
    - 打开 `变体`。
    - 在主工作区 `VariantCreationComposer` 填写 1001 字符 `summary`。
    - 点击 `创建约束 variant`。
    - 断言 `.variantCreationComposer .formErrorSummary` 可见，`textarea[name="summary"]` 有 `aria-invalid="true"`。
    - 再用候选版本 composer 的 1001 字符 `change_summary` 验证 `.workspaceVersionComposer .formErrorSummary`。

- [x] **Step 2: 跑 E2E 红灯**
  - Run: `cd apps/web && npm run e2e -- form-errors.spec.ts -g "variant workspace field errors"`
  - Expected: FAIL，因为主工作区变体表单还不是 `ValidatedForm`，mutation handler 也不 rethrow API 字段错误。

- [x] **Step 3: 接入共享表单基础件**
  - `VariantCreationComposer` 使用 `ValidatedForm`，字段改为 `TextField` / `TextAreaField` / `CheckboxField`。
  - `WorkspaceVersionComposer` 使用 `ValidatedForm`，字段改为 `SelectField` / `FileField` / `TextAreaField` / `CheckboxField`。
  - 保留原有 className，避免视觉基线大幅变化。

- [x] **Step 4: 让 handler 抛回字段错误**
  - `createVariant` 调 `runCommand(..., { rethrowFieldErrors: true })`。
  - `createVariantVersion` 调 `runCommand(..., { rethrowFieldErrors: true })`。

- [x] **Step 5: 跑 E2E 绿灯**
  - Run: `cd apps/web && npm run e2e -- form-errors.spec.ts -g "variant workspace field errors"`
  - Expected: PASS。

### Task 3: 文档、完整验证、提交

**Files:**
- Modify: `README.md`
- Modify: `docs/api-contract.md`
- Modify: `docs/product-ux-review.md`
- Modify: `docs/product-ux-friction-audit-2026-05-14.md`
- Modify: `docs/product-completion-audit-2026-05-08.md`
- Modify: `.agent/logs/LOG.md`
- Modify: `.agent/tasks.json`
- Create: `.agent/tasks/TASK-063.json`

- [x] **Step 1: 更新中文文档和任务记录**
  - 记录 variant label / summary / change summary 上限。
  - 记录主工作区 variant 表单已接入字段错误。

- [x] **Step 2: 完整验证**
  - `cd apps/api && UV_NO_CACHE=1 uv run pytest`
  - `cd apps/web && npm run test:unit`
  - `cd apps/web && npm run typecheck`
  - `cd apps/web && npm run build`
  - `cd apps/web && npm audit --omit=dev`
  - `cd apps/web && npm run e2e`
  - `git diff --check`
  - `jq empty .agent/tasks.json .agent/tasks/TASK-063.json`
