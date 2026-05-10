# 快速添加测试用例实现计划

> **给 agentic workers:** 必须按任务逐步执行；步骤使用 checkbox (`- [ ]`) 记录状态。

**目标:** 让用户在测评页快速添加单条或批量测试用例，并让批量添加只生成一个新的 `EvalSetVersion`。

**架构:** 后端新增 batch command，复用现有 artifacts、eval case、eval set version 表结构，不引入新表。前端新增独立 `QuickAddCases` 客户端组件，`DecisionWorkbench` 只负责调用 API 和刷新当前 skill。

**技术栈:** FastAPI、SQLAlchemy Core、SQLite、Next.js App Router、React 19 client components、TypeScript、Playwright E2E、现有全局 CSS。

---

### Task 1: 后端红测和 batch command

**文件:**
- 修改: `apps/api/tests/test_sql_repository.py`
- 修改: `apps/api/tests/test_api_commands.py`
- 修改: `apps/api/skillhub/infrastructure/db/repositories.py`
- 修改: `apps/api/skillhub/api/main.py`

- [x] **Step 1: 写 repository 红测**

在 `SqlSkillRepositoryTest` 中新增测试：创建 skill 后调用 `create_eval_cases_batch` 添加两条 case，断言只新增一个 eval set version，且 membership 包含两条新增 case version。

- [x] **Step 2: 写 API 红测**

在 `ApiCommandTest` 中新增测试：`POST /api/eval-cases/batch` 返回两条 created，并且 `GET /api/eval-set-versions/{id}` 能看到两条具体 case。

- [x] **Step 3: 运行红测**

```bash
cd apps/api && uv run pytest tests/test_sql_repository.py::SqlSkillRepositoryTest::test_create_eval_cases_batch_creates_one_eval_set_snapshot tests/test_api_commands.py::ApiCommandTest::test_batch_eval_cases_endpoint_creates_one_snapshot
```

预期：失败，因为 repository method 和 API endpoint 还不存在。

- [x] **Step 4: 实现 repository method**

新增 `create_eval_cases_batch(...)`，在一个 transaction 中插入所有 case、case version、artifacts，然后创建一个 eval set version。

- [x] **Step 5: 实现 FastAPI payload 和 endpoint**

新增 `CreateEvalCaseItemPayload`、`CreateEvalCasesBatchPayload` 和 `POST /api/eval-cases/batch`。

- [x] **Step 6: 运行后端测试**

```bash
cd apps/api && uv run pytest
```

预期：全部通过。

### Task 2: 前端红测和快速添加组件

**文件:**
- 修改: `apps/web/e2e/skills-workbench.spec.ts`
- 新增: `apps/web/components/eval-cases/quick-add-cases.tsx`
- 修改: `apps/web/components/decision-workbench.tsx`
- 修改: `apps/web/app/globals.css`

- [x] **Step 1: 写 E2E 红测**

新增测试 `operator can batch paste eval cases and record a run`：导入 skill，进入测评页，在批量 textarea 粘贴两行 `title | input | expected`，提交后看到两张 case 卡片，分别确认通过/不通过并记录 run。

- [x] **Step 2: 运行红测**

```bash
cd apps/web && npm run e2e -- --grep "batch paste eval cases"
```

预期：失败，因为页面还没有快速添加面板。

- [x] **Step 3: 实现 `QuickAddCases`**

组件包含单条快加、批量粘贴、解析预览、无效行提示，并通过 `onCreateCases` 提交结构化 drafts。

- [x] **Step 4: 接入 `DecisionWorkbench`**

新增 `createCases` 方法调用 `POST /api/eval-cases/batch`，并把 `QuickAddCases` 放进 `EvalsPane` 的测评目标和进度条之间。

- [x] **Step 5: 添加样式**

新增 `.quickCaseComposer`、`.quickCaseModeSwitch`、`.quickCaseGrid`、`.quickCaseBatchPreview` 等样式，保持与当前工作台视觉一致。

- [x] **Step 6: 运行前端局部验证**

```bash
cd apps/web && npm run typecheck
cd apps/web && npm run e2e -- --grep "batch paste eval cases"
```

预期：全部通过。

### Task 3: 文档、全量验证、提交推送

**文件:**
- 修改: `.agent/tasks.json`
- 新增: `.agent/tasks/TASK-006.json`
- 修改: `README.md`
- 修改: `docs/product-ux-review.md`
- 修改: `docs/product-completion-audit-2026-05-08.md`

- [x] **Step 1: 更新文档**

README 增加批量添加 case 的试用路径；UX 评审记录 TestRail/Airtable/Linear 借鉴点；完成度审计补上快速添加 case 的证据和仍未完成风险。

- [x] **Step 2: 全量验证**

```bash
cd apps/api && uv run pytest
cd apps/web && npm run typecheck
cd apps/web && npm run build
cd apps/web && npm run e2e
git diff --check
```

- [x] **Step 3: 提交推送**

```bash
git add .
git commit -m "feat: add fast eval case entry"
git push
```

## 自检

- 保持 case 严谨性：批量导入仍要求 input 和 expected output。
- 降低版本噪音：一次批量写入只生成一个 `EvalSetVersion`。
- 控制范围：不做 CSV 文件上传、模板系统、矩阵查询或 restore。
