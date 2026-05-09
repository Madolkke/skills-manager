# Run And Case History Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a first-class history surface so operators can inspect eval run history, filter exact version bindings, and review eval case version timelines inside the `/skills` workbench.

**Architecture:** Add two backend read models without changing the write model: `list_eval_runs_for_skill(...)` and `eval_case_history(...)`. Add matching FastAPI routes and TypeScript types, then render a History tab plus an inline case history panel in the existing tri-pane workbench. Keep the UI in the same refined Linear-style workbench language, with compact filters and evidence-first details.

**Tech Stack:** FastAPI, SQLAlchemy Core, SQLite, Next.js React client component, TypeScript, Playwright E2E, existing visual regression setup.

---

### Task 1: Backend Run History Read Model

**Files:**
- Modify: `apps/api/tests/test_api_commands.py`
- Modify: `apps/api/skillhub/infrastructure/db/repositories.py`
- Modify: `apps/api/skillhub/api/main.py`

- [x] **Step 1: Write failing API tests**

Add tests to `ApiCommandTest`:

```python
def test_eval_run_history_filters_by_variant_eval_set_strategy_status(self):
    skill = self.create_skill("history-reviewer")
    first_case = self.client.post("/api/eval-cases", json={
        "skill_id": skill["skill_id"],
        "title": "PR: missing tenant filter",
        "input_text": "return Project.all()",
        "expected_output": "Flag missing tenant scope.",
        "actor": "tester",
    }).json()
    second_version = self.client.post("/api/variant-versions", json={
        "variant_id": skill["variant_id"],
        "content_ref": {"kind": "skill_bundle", "locator": "memory:v2", "digest": "digest-v2"},
        "change_summary": "Add stricter review rules.",
        "make_current": True,
        "actor": "tester",
    }).json()
    first_run = self.client.post("/api/eval-runs", json={
        "variant_version_id": skill["variant_version_id"],
        "eval_set_version_id": first_case["eval_set_version_id"],
        "strategy": "manual_pass_fail",
        "results": {first_case["eval_case_version_id"]: True},
        "actor": "tester",
    }).json()
    second_run = self.client.post("/api/eval-runs", json={
        "variant_version_id": second_version["variant_version_id"],
        "eval_set_version_id": first_case["eval_set_version_id"],
        "strategy": "manual_pass_fail",
        "results": {first_case["eval_case_version_id"]: False},
        "actor": "tester",
    }).json()

    history = self.client.get(
        f"/api/skills/{skill['skill_id']}/eval-runs",
        params={
            "variant_version_id": second_version["variant_version_id"],
            "eval_set_version_id": first_case["eval_set_version_id"],
            "strategy": "manual_pass_fail",
            "status": "finished",
        },
    )

    self.assertEqual(history.status_code, 200)
    self.assertEqual([row["eval_run"]["id"] for row in history.json()["runs"]], [second_run["eval_run_id"]])
    row = history.json()["runs"][0]
    self.assertEqual(row["variant_version"]["version_number"], 2)
    self.assertEqual(row["eval_set_version"]["id"], first_case["eval_set_version_id"])
    self.assertEqual(row["variant"]["label"], "Baseline")
    self.assertEqual(row["eval_run"]["summary"], {"passed": 0, "failed": 1, "total": 1})
    self.assertNotEqual(first_run["eval_run_id"], second_run["eval_run_id"])

def test_eval_run_history_orders_newest_first_and_limits_results(self):
    skill = self.create_skill("history-limit-reviewer")
    case = self.client.post("/api/eval-cases", json={
        "skill_id": skill["skill_id"],
        "title": "PR: missing owner check",
        "input_text": "Project.query.all()",
        "expected_output": "Flag missing owner check.",
        "actor": "tester",
    }).json()
    run_ids = []
    for _ in range(3):
        run = self.client.post("/api/eval-runs", json={
            "variant_version_id": skill["variant_version_id"],
            "eval_set_version_id": case["eval_set_version_id"],
            "strategy": "manual_pass_fail",
            "results": {case["eval_case_version_id"]: True},
            "actor": "tester",
        }).json()
        run_ids.append(run["eval_run_id"])

    history = self.client.get(f"/api/skills/{skill['skill_id']}/eval-runs", params={"limit": 2})

    self.assertEqual(history.status_code, 200)
    self.assertEqual([row["eval_run"]["id"] for row in history.json()["runs"]], list(reversed(run_ids[-2:])))
```

- [x] **Step 2: Run the failing backend tests**

Run:

```bash
cd apps/api
uv run pytest tests/test_api_commands.py -k "eval_run_history" -v
```

Expected: FAIL with 404 because `/api/skills/{skill_id}/eval-runs` does not exist.

- [x] **Step 3: Implement repository read model**

Add `list_eval_runs_for_skill(...)` to `SqlSkillRepository`. It should:

- confirm the skill exists with `_skill_row`.
- filter by optional `variant_version_id`, `eval_set_version_id`, `strategy`, `status`.
- clamp `limit` to `1..200`, defaulting to `50`.
- order by `created_at desc`, then `id desc`.
- join each run to variant version, variant, eval set version, and eval set.
- return `{ "skill": ..., "runs": [...] }`.

- [x] **Step 4: Implement FastAPI route**

Add:

```python
@app.get("/api/skills/{skill_id}/eval-runs")
def eval_run_history(
    skill_id: str,
    variant_version_id: str | None = None,
    eval_set_version_id: str | None = None,
    strategy: str | None = None,
    status: str | None = None,
    limit: int = 50,
    repository: SqlSkillRepository = Depends(repository_dependency),
):
    return result_payload(
        repository.list_eval_runs_for_skill(
            skill_id=skill_id,
            variant_version_id=variant_version_id,
            eval_set_version_id=eval_set_version_id,
            strategy=strategy,
            status=status,
            limit=limit,
        )
    )
```

- [x] **Step 5: Verify backend run history tests pass**

Run:

```bash
cd apps/api
uv run pytest tests/test_api_commands.py -k "eval_run_history" -v
```

Expected: PASS.

### Task 2: Backend Case Version History Read Model

**Files:**
- Modify: `apps/api/tests/test_api_commands.py`
- Modify: `apps/api/skillhub/infrastructure/db/repositories.py`
- Modify: `apps/api/skillhub/api/main.py`

- [x] **Step 1: Write failing API tests**

Add tests to `ApiCommandTest`:

```python
def test_eval_case_history_returns_versions_and_eval_set_membership(self):
    skill = self.create_skill("case-history-reviewer")
    case = self.client.post("/api/eval-cases", json={
        "skill_id": skill["skill_id"],
        "title": "PR: stale title",
        "input_text": "return Project.find_many()",
        "expected_output": "Flag missing tenant scope.",
        "notes": "Original customer regression.",
        "actor": "tester",
    }).json()
    revised = self.client.patch(f"/api/eval-cases/{case['eval_case_id']}", json={
        "case_id": case["eval_case_id"],
        "title": "PR: edited owner filter",
        "input_text": "return Project.find_many({})",
        "expected_output": "Must flag missing owner or tenant scope.",
        "notes": "Clarified expected finding.",
        "actor": "tester",
        "make_current": True,
    }).json()

    history = self.client.get(f"/api/eval-cases/{case['eval_case_id']}/versions")

    self.assertEqual(history.status_code, 200)
    payload = history.json()
    self.assertEqual(payload["case"]["title"], "PR: edited owner filter")
    self.assertEqual([item["case_version"]["version_number"] for item in payload["versions"]], [2, 1])
    self.assertEqual(payload["versions"][0]["case_version"]["notes"], "Clarified expected finding.")
    self.assertIn("missing owner", payload["versions"][0]["case_version"]["expected_output_artifact"]["content_text"])
    self.assertEqual(payload["versions"][0]["included_in_eval_set_versions"][0]["id"], revised["eval_set_version_id"])
    self.assertEqual(payload["versions"][1]["included_in_eval_set_versions"][0]["id"], case["eval_set_version_id"])

def test_eval_case_history_reads_archived_case(self):
    skill = self.create_skill("archived-case-history-reviewer")
    case = self.client.post("/api/eval-cases", json={
        "skill_id": skill["skill_id"],
        "title": "PR: archive me",
        "input_text": "rename only",
        "expected_output": "No finding",
        "actor": "tester",
    }).json()
    self.client.delete(f"/api/eval-cases/{case['eval_case_id']}")

    history = self.client.get(f"/api/eval-cases/{case['eval_case_id']}/versions")

    self.assertEqual(history.status_code, 200)
    self.assertEqual(history.json()["case"]["lifecycle_status"], "archived")
    self.assertEqual(history.json()["versions"][0]["case_version"]["version_number"], 1)
```

- [x] **Step 2: Run the failing backend tests**

Run:

```bash
cd apps/api
uv run pytest tests/test_api_commands.py -k "eval_case_history" -v
```

Expected: FAIL with 404 because `/api/eval-cases/{case_id}/versions` does not exist.

- [x] **Step 3: Implement repository read model**

Add `eval_case_history(case_id)` to `SqlSkillRepository`. It should:

- read the case even if archived.
- fetch all `eval_case_versions` for the case, newest first.
- attach `input_artifact` and `expected_output_artifact` using `_case_version_detail`.
- attach all `eval_set_case_versions` memberships, joined to `eval_set_versions`, ordered newest first.

- [x] **Step 4: Implement FastAPI route**

Add:

```python
@app.get("/api/eval-cases/{case_id}/versions")
def eval_case_history(case_id: str, repository: SqlSkillRepository = Depends(repository_dependency)):
    return result_payload(repository.eval_case_history(case_id))
```

- [x] **Step 5: Verify backend case history tests pass**

Run:

```bash
cd apps/api
uv run pytest tests/test_api_commands.py -k "eval_case_history" -v
```

Expected: PASS.

### Task 3: Frontend Types And API Wiring

**Files:**
- Modify: `apps/web/lib/types.ts`
- Modify: `apps/web/components/decision-workbench.tsx`

- [x] **Step 1: Add TypeScript types**

Add `EvalRunHistory`, `EvalRunHistoryRow`, `EvalCaseHistory`, and `EvalCaseHistoryVersion` to `apps/web/lib/types.ts`, matching the API response shape in the design spec.

- [x] **Step 2: Add client state and loaders**

In `DecisionWorkbench`, add state for:

- `runHistory`
- `runHistoryLoading`
- `selectedRunId`
- `runFilters`
- `caseHistory`
- `caseHistoryLoading`
- `caseHistoryCaseId`

Add loaders:

- `loadRunHistory(skillId, filters)`
- `loadCaseHistory(caseId)`

Use existing `apiGet` and keep fetches event-driven or tied to `mode === "history"` / explicit case-history clicks.

- [x] **Step 3: Verify typecheck fails only before implementation and passes after wiring**

Run:

```bash
cd apps/web
npm run typecheck
```

Expected after implementation: PASS.

### Task 4: Frontend History UI

**Files:**
- Modify: `apps/web/components/decision-workbench.tsx`
- Modify: `apps/web/app/globals.css`
- Modify: `apps/web/e2e/helpers.ts`
- Modify: `apps/web/e2e/skills-workbench.spec.ts`

- [x] **Step 1: Write failing Playwright tests**

Add two tests:

```ts
test("operator can review eval run history with filters", async ({ page }) => {
  const skillName = `history-reviewing-${Date.now()}`;
  await importSkillBundle(page, skillName);
  await addEvalCase(page, "PR: missing tenant scope");
  await page.locator(".caseReviewCard").filter({ hasText: "PR: missing tenant scope" }).getByRole("button", { name: "通过", exact: true }).click();
  await page.getByTestId("eval-run-bar").getByRole("button", { name: "记录本次测评" }).click();
  await expect(page.getByText("已记录 1/1 通过。")).toBeVisible();
  await page.locator(".caseReviewCard").filter({ hasText: "PR: missing tenant scope" }).getByRole("button", { name: "不通过", exact: true }).click();
  await page.getByTestId("eval-run-bar").getByRole("button", { name: "记录本次测评" }).click();
  await expect(page.getByText("已记录 0/1 通过。")).toBeVisible();

  await page.getByRole("button", { name: "历史" }).click();
  await expect(page.locator(".historyRunRow")).toHaveCount(2);
  await expect(page.getByText("0/1")).toBeVisible();
  await page.getByLabel("Strategy filter").selectOption("manual_pass_fail");
  await expect(page.locator(".historyRunRow")).toHaveCount(2);
  await expect(page.getByText("PR: missing tenant scope")).toBeVisible();
});

test("operator can inspect eval case version history", async ({ page }) => {
  await importSkillBundle(page, `case-history-${Date.now()}`);
  await addEvalCase(page, "PR: stale case wording");
  await page.getByLabel("Inspector").getByRole("button", { name: "编辑 case" }).click();
  await page.getByPlaceholder("新标题").fill("PR: edited case wording");
  await page.getByPlaceholder("新的 input").fill("diff --git a/service.py b/service.py\n+return Project.find_many({})");
  await page.getByPlaceholder("新的 expected output").fill("Must flag missing tenant scope.");
  await page.getByPlaceholder("为什么更新").fill("Clarified tenant-scope expected result.");
  await page.getByRole("button", { name: "保存 case version" }).click();

  await page.locator(".caseReviewCard").filter({ hasText: "PR: edited case wording" }).getByRole("button", { name: "历史" }).click();
  await expect(page.getByText("Case version history")).toBeVisible();
  await expect(page.getByText("v2")).toBeVisible();
  await expect(page.getByText("v1")).toBeVisible();
  await expect(page.getByText("Clarified tenant-scope expected result.")).toBeVisible();
  await expect(page.getByText("Must flag missing tenant scope.")).toBeVisible();
});
```

- [x] **Step 2: Run failing E2E tests**

Run:

```bash
cd apps/web
npm run e2e -- --grep "history"
```

Expected: FAIL because the History tab and case history button do not exist.

- [x] **Step 3: Add History tab and run table**

Add `mode === "history"` to tabs. Render `HistoryPane` with:

- compact filters.
- `.historyRunRow` buttons.
- selected run summary.
- case result list.
- empty state linking to `测评`.

- [x] **Step 4: Add case version timeline**

Add a `历史` button to each case card. When clicked, load `GET /api/eval-cases/{case_id}/versions` and show a `CaseHistoryPanel` in the case detail area.

- [x] **Step 5: Style History UI**

Add CSS classes:

- `.historyPane`
- `.historyFilters`
- `.historyGrid`
- `.historyRunRow`
- `.historyRunRowActive`
- `.historyRunDetail`
- `.caseHistoryTimeline`
- `.caseHistoryVersion`

Use the existing restrained product palette and avoid visual novelty that fights the workbench.

- [x] **Step 6: Verify targeted E2E passes**

Run:

```bash
cd apps/web
npm run e2e -- --grep "history"
```

Expected: PASS.

### Task 5: Docs, Full Verification, Commit, Push

**Files:**
- Modify: `README.md`
- Modify: `docs/product-ux-review.md`
- Modify: `docs/product-completion-audit-2026-05-08.md`
- Modify: `docs/superpowers/plans/2026-05-09-run-case-history.md`

- [x] **Step 1: Update docs**

Update README product flow to mention History tab and case version history. Update UX review and completion audit so run history / case history move from missing to implemented, while keeping remaining gaps explicit.

- [x] **Step 2: Run full verification**

Run:

```bash
cd apps/api && uv run pytest
cd apps/web && npm run typecheck
cd apps/web && npm run build
cd apps/web && npm run e2e
git diff --check
```

Expected: all pass.

- [x] **Step 3: Mark this plan complete**

Change all completed task checkboxes to `[x]`.

- [x] **Step 4: Commit and push**

Run:

```bash
git add README.md docs/product-ux-review.md docs/product-completion-audit-2026-05-08.md docs/superpowers/plans/2026-05-09-run-case-history.md apps/api apps/web
git commit -m "Implement run and case history"
git push origin main
```

Expected: push succeeds and `git status --short` is clean.

## Self-Review

Spec coverage:

- Task 1 covers eval run history read model, filters, exact binding display, ordering, and limit.
- Task 2 covers case version history, artifact content, eval set membership, and archived case readability.
- Task 3 covers frontend type contracts and API loading.
- Task 4 covers History tab, run detail, filter UI, and case version timeline.
- Task 5 covers README, UX review, completion audit, verification, and push.

Placeholder scan:

- No placeholder markers or deferred requirements.

Type consistency:

- Route names match the spec: `/api/skills/{skill_id}/eval-runs` and `/api/eval-cases/{case_id}/versions`.
- Frontend entity names use `EvalRunHistory`, `EvalRunHistoryRow`, `EvalCaseHistory`, and `EvalCaseHistoryVersion`.
