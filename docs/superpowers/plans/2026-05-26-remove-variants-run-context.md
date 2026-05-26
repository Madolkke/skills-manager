# Remove Variants Run Context Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace user-facing and core Variant/VariantVersion semantics with direct SkillVersion content versions and EvalRun run context.

**Architecture:** The new fact model is `Skill -> SkillVersion -> EvalRun(run_context) + EvalSetVersion`. Runtime environment tags move from variant tag sets to `EvalRun.environment_tags` and `EvalRun.run_context`; history, diff, accepted verification, Web V4 pages, and docs read from that model. Existing local data is migrated by copying old `variant_versions` into `skill_versions`, reassigning per-skill version numbers, and moving old variant tags onto historical eval runs.

**Tech Stack:** FastAPI, Pydantic, SQLAlchemy Core, SQLite/Postgres-compatible DDL, Alembic migrations, React/Vite/TypeScript, Vitest, Playwright.

---

## File Structure

- `apps/api/skillhub/infrastructure/db/schema.sql`: authoritative fresh schema; remove variant/tag tables and add `skill_versions`, `skills.current_version_id`, EvalRun context fields.
- `apps/api/skillhub/infrastructure/db/tables.py`: SQLAlchemy metadata mirror of the schema.
- `apps/api/migrations/versions/0001_initial_schema.py`: downgrade list must drop new tables and stop dropping removed tables.
- `apps/api/migrations/versions/0002_remove_variants_run_context.py`: online migration from old local databases.
- `apps/api/skillhub/domain/models.py`: rename dataclasses and ids to SkillVersion; keep `normalize_tags` only for EvalRun environment tags.
- `apps/api/skillhub/infrastructure/db/repositories.py`: replace create/read/update logic that references variants with skill version logic; remove promotion review methods.
- `apps/api/skillhub/api/main.py`: update request/response payloads and routes.
- `apps/api/tests/*.py`: rewrite schema, repository, and API tests to assert no Variant core model and context-aware runs.
- `apps/web-v4/src/types.ts`: replace Variant types with SkillVersion types and add EvalRun context types.
- `apps/web-v4/src/lib/api.ts`: use `/api/skill-versions`, `/api/artifacts/diff?left_skill_version_id=...`, and `skill_version_id`.
- `apps/web-v4/src/pages/*` and `apps/web-v4/src/components/*`: rename Variants page to Versions page, remove tag requirements from create/upload, add run environment inputs to manual eval, update history.
- `apps/web-v4/e2e/*`: update seed, formal flow, responsive smoke, and visual smoke.
- `README.md`, `docs/api-contract.md`, `docs/formal-architecture-v0.1.md`, new audit doc: explain SkillVersion + EvalRun context.

---

### Task 1: Schema Contract Red Tests

**Files:**
- Modify: `apps/api/tests/test_schema_contract.py`
- Modify: `apps/api/tests/test_sqlalchemy_metadata.py`

- [ ] **Step 1: Replace table expectations**

In `test_core_tables_exist`, expect `skill_versions` and remove `tag_sets`, `variants`, `variant_versions`, and `promotion_decisions`.

```python
for table in [
    "artifacts",
    "skills",
    "skill_versions",
    "eval_sets",
    "eval_cases",
    "eval_case_versions",
    "eval_set_versions",
    "eval_set_case_versions",
    "eval_runs",
    "case_results",
    "accepted_verifications",
    "saved_views",
    "jobs",
    "role_assignments",
    "audit_events",
]:
    self.assertIn(f"create table {table}", self.normalized)
```

- [ ] **Step 2: Replace same-skill invariant assertions**

In `test_run_same_skill_invariant_is_enforced_by_composite_foreign_keys`, assert:

```python
self.assertIn(
    "foreign key (skill_version_id, skill_id) references skill_versions(id, skill_id)",
    self.normalized,
)
self.assertIn(
    "foreign key (eval_set_version_id, skill_id) references eval_set_versions(id, skill_id)",
    self.normalized,
)
```

- [ ] **Step 3: Add EvalRun context schema assertions**

Add a test:

```python
def test_eval_runs_store_run_context(self):
    for snippet in [
        "skill_version_id text not null",
        "environment_tags text[] not null",
        "run_context jsonb not null",
        "run_context_hash text not null",
        "create index eval_runs_skill_version_id_idx",
        "create index eval_runs_context_hash_idx",
    ]:
        self.assertIn(snippet, self.normalized)
```

- [ ] **Step 4: Update SQLAlchemy metadata tests**

Replace references to `tables.variant_versions` with `tables.skill_versions`, and assert:

```python
self.assert_foreign_key(
    "eval_runs",
    "eval_runs_skill_version_skill_fkey",
    ("skill_version_id", "skill_id"),
    "skill_versions",
)
self.assert_unique_constraint(
    "skill_versions",
    "skill_versions_skill_version_unique",
    ("skill_id", "version_number"),
)
self.assert_index("eval_runs", "eval_runs_skill_version_id_idx")
```

- [ ] **Step 5: Run red tests**

Run:

```bash
cd apps/api
uv run pytest tests/test_schema_contract.py tests/test_sqlalchemy_metadata.py -q
```

Expected: FAIL because the schema still contains variant tables and lacks `skill_versions`.

---

### Task 2: Schema, Metadata, and Migration Implementation

**Files:**
- Modify: `apps/api/skillhub/infrastructure/db/schema.sql`
- Modify: `apps/api/skillhub/infrastructure/db/tables.py`
- Modify: `apps/api/migrations/versions/0001_initial_schema.py`
- Create: `apps/api/migrations/versions/0002_remove_variants_run_context.py`

- [ ] **Step 1: Add `skill_versions` to schema.sql**

Replace the old `tag_sets`, `variants`, and `variant_versions` block with:

```sql
create table skills (
  id text primary key,
  slug text not null unique,
  owner_ref text not null,
  current_version_id text,
  lifecycle_status text not null default 'active',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint skills_lifecycle_status_check check (lifecycle_status in ('active', 'archived'))
);

create table skill_versions (
  id text primary key,
  skill_id text not null references skills(id),
  version_number integer not null,
  content_ref jsonb not null,
  content_digest text not null,
  change_summary text not null,
  created_at timestamptz not null default now(),
  created_by text not null,
  constraint skill_versions_version_number_positive check (version_number > 0),
  constraint skill_versions_skill_version_unique unique (skill_id, version_number),
  constraint skill_versions_id_skill_unique unique (id, skill_id)
);

alter table skills
  add constraint skills_current_version_fkey
  foreign key (current_version_id, id) references skill_versions(id, skill_id);
```

- [ ] **Step 2: Update `eval_runs` and `accepted_verifications` DDL**

Use:

```sql
create table eval_runs (
  id text primary key,
  skill_id text not null,
  skill_version_id text not null,
  eval_set_version_id text not null,
  strategy text not null,
  status text not null,
  environment_tags text[] not null default '{}',
  run_context jsonb not null default '{}'::jsonb,
  run_context_hash text not null,
  summary jsonb not null default '{}'::jsonb,
  result_artifact_id text references artifacts(id),
  created_at timestamptz not null default now(),
  created_by text not null,
  constraint eval_runs_status_check check (status in ('queued', 'running', 'finished', 'failed')),
  constraint eval_runs_id_skill_unique unique (id, skill_id),
  constraint eval_runs_skill_version_skill_fkey foreign key (skill_version_id, skill_id) references skill_versions(id, skill_id),
  constraint eval_runs_eval_set_version_skill_fkey foreign key (eval_set_version_id, skill_id) references eval_set_versions(id, skill_id)
);

create table accepted_verifications (
  id text primary key,
  skill_id text not null,
  skill_version_id text not null,
  eval_set_version_id text not null,
  run_context_hash text not null,
  eval_run_id text not null,
  note text not null default '',
  created_at timestamptz not null default now(),
  created_by text not null,
  constraint accepted_verifications_id_skill_unique unique (id, skill_id),
  constraint accepted_verifications_context_unique unique (skill_id, skill_version_id, eval_set_version_id, run_context_hash),
  constraint accepted_verifications_skill_version_skill_fkey foreign key (skill_version_id, skill_id) references skill_versions(id, skill_id),
  constraint accepted_verifications_eval_set_version_skill_fkey foreign key (eval_set_version_id, skill_id) references eval_set_versions(id, skill_id),
  constraint accepted_verifications_eval_run_skill_fkey foreign key (eval_run_id, skill_id) references eval_runs(id, skill_id)
);
```

- [ ] **Step 3: Add indexes**

Use:

```sql
create index skill_versions_skill_id_idx on skill_versions (skill_id);
create index eval_runs_skill_version_id_idx on eval_runs (skill_version_id);
create index eval_runs_context_hash_idx on eval_runs (run_context_hash);
create index accepted_verifications_context_idx on accepted_verifications (skill_id, skill_version_id, eval_set_version_id, run_context_hash);
```

- [ ] **Step 4: Mirror the schema in `tables.py`**

Create a `skill_versions = Table(...)` with the same fields and constraints. Remove `tag_sets`, `variants`, `variant_versions`, and `promotion_decisions` table definitions. Change `eval_runs.c.variant_version_id` to `eval_runs.c.skill_version_id`, add `environment_tags`, `run_context`, and `run_context_hash`.

- [ ] **Step 5: Add Alembic migration**

Create `0002_remove_variants_run_context.py` with `revision = "0002_remove_variants_run_context"` and `down_revision = "0001_initial_schema"`.

Upgrade algorithm:

```python
from alembic import op
import sqlalchemy as sa

def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "skill_versions" in inspector.get_table_names():
        return
    op.execute("create table skill_versions (...)")
    op.execute(
        """
        insert into skill_versions (id, skill_id, version_number, content_ref, content_digest, change_summary, created_at, created_by)
        select id, skill_id,
               row_number() over (partition by skill_id order by created_at, id) as version_number,
               content_ref, content_digest, change_summary, created_at, created_by
        from variant_versions
        """
    )
    op.add_column("skills", sa.Column("current_version_id", sa.Text(), nullable=True))
    op.execute(
        """
        update skills
        set current_version_id = (
          select variants.current_version_id
          from variants
          where variants.id = skills.default_variant_id
        )
        """
    )
    op.add_column("eval_runs", sa.Column("skill_version_id", sa.Text(), nullable=True))
    op.add_column("eval_runs", sa.Column("environment_tags", sa.JSON(), nullable=True))
    op.add_column("eval_runs", sa.Column("run_context", sa.JSON(), nullable=True))
    op.add_column("eval_runs", sa.Column("run_context_hash", sa.Text(), nullable=True))
    op.execute("update eval_runs set skill_version_id = variant_version_id")
    # SQLite-safe context backfill is finalized in Task 4 helper tests.
```

Then rebuild fresh schemas from `schema.sql` for normal app startup. Do not rely on 0002 for tests that instantiate fresh metadata.

- [ ] **Step 6: Run schema tests**

Run:

```bash
cd apps/api
uv run pytest tests/test_schema_contract.py tests/test_sqlalchemy_metadata.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add apps/api/skillhub/infrastructure/db/schema.sql apps/api/skillhub/infrastructure/db/tables.py apps/api/migrations/versions apps/api/tests/test_schema_contract.py apps/api/tests/test_sqlalchemy_metadata.py
git commit -m "refactor: replace variants with skill versions schema"
```

---

### Task 3: Repository and API Red Tests

**Files:**
- Modify: `apps/api/tests/test_sql_repository.py`
- Modify: `apps/api/tests/test_api_commands.py`
- Modify: `apps/api/tests/test_domain_invariants.py`

- [ ] **Step 1: Rename helper results**

Change expected helper dict keys from `variant_id` / `variant_version_id` to `skill_version_id`.

Example assertion:

```python
created = self.repository.create_skill(...)
self.assertTrue(created.skill_version_id.startswith("skillver_"))
detail = self.repository.skill_detail(created.skill_id)
self.assertEqual(detail["summary"]["current_version"]["id"], created.skill_version_id)
```

- [ ] **Step 2: Add run context test**

Add:

```python
def test_record_eval_run_persists_environment_context(self):
    skill = self.create_skill("context-run")
    case = self.create_case(skill.skill_id)
    run = self.repository.record_eval_run(
        skill_version_id=skill.skill_version_id,
        eval_set_version_id=case.eval_set_version_id,
        strategy="manual_pass_fail",
        environment_tags=["windows", "codex", "windows"],
        run_context={"runner": "codex", "os": "windows"},
        results={case.eval_case_version_id: {"passed": True, "actual_output": "ok"}},
        actor="tester",
    )
    detail = self.repository.eval_run_detail(run.eval_run_id)
    self.assertEqual(detail["eval_run"]["environment_tags"], ["codex", "windows"])
    self.assertEqual(detail["eval_run"]["run_context"]["runner"], "codex")
    self.assertEqual(detail["skill_version"]["id"], skill.skill_version_id)
```

- [ ] **Step 3: Add API contract test**

Post to `/api/eval-runs` with `skill_version_id`, `environment_tags`, and `run_context`; assert response is 200 and detail returns those fields.

- [ ] **Step 4: Add negative API test**

Post old payload with `variant_version_id` and no `skill_version_id`; assert `422` and field error for `skill_version_id`.

- [ ] **Step 5: Run red tests**

Run:

```bash
cd apps/api
uv run pytest tests/test_sql_repository.py::SqlSkillRepositoryTest::test_record_eval_run_persists_environment_context tests/test_api_commands.py::ApiCommandTest::test_command_flow_records_eval_run -q
```

Expected: FAIL because repository/API still use variant fields.

---

### Task 4: Repository Implementation

**Files:**
- Modify: `apps/api/skillhub/domain/models.py`
- Modify: `apps/api/skillhub/infrastructure/db/repositories.py`
- Modify: `apps/api/skillhub/domain/permissions.py`
- Modify: `apps/api/tests/test_saved_views.py`

- [ ] **Step 1: Rename dataclasses**

In `domain/models.py`, remove `TagSet`, `Variant`, and `VariantVersion`; add:

```python
@dataclass(frozen=True)
class Skill:
    id: str
    slug: str
    owner_ref: str
    current_version_id: str | None
    created_at: datetime
    lifecycle_status: LifecycleStatus = "active"

@dataclass(frozen=True)
class SkillVersion:
    id: str
    skill_id: str
    version_number: int
    content_ref: ContentRef
    change_summary: str
    created_at: datetime
    created_by: str
```

- [ ] **Step 2: Rename result dataclasses**

In `repositories.py`, replace:

```python
class CreateSkillResult:
    skill_id: str
    eval_set_id: str
    eval_set_version_id: str
    skill_version_id: str

class CreateSkillVersionResult:
    skill_id: str
    skill_version_id: str
    version_number: int

class RecordEvalRunResult:
    eval_run_id: str
    skill_id: str
    skill_version_id: str
    eval_set_version_id: str
    passed: int
    failed: int
    total: int
```

- [ ] **Step 3: Rework `create_skill`**

Signature:

```python
def create_skill(self, *, slug: str, owner_ref: str, content_ref: ContentRef, change_summary: str, actor: str) -> CreateSkillResult:
```

Implementation:

- Insert `skills` with `current_version_id=None`.
- Insert primary eval set and eval set version.
- Insert `skill_versions` v1 with `id=new_id("skillver")`.
- Update `skills.current_version_id`.
- Grant owner role and audit as today.

- [ ] **Step 4: Rework version creation**

Replace `create_variant_version` and `create_variant` with:

```python
def create_skill_version(self, *, skill_id: str, content_ref: ContentRef, change_summary: str, actor: str, make_current: bool) -> CreateSkillVersionResult:
```

Use `_next_skill_version_number(connection, skill_id)` and insert into `tables.skill_versions`.

- [ ] **Step 5: Rework `record_eval_run`**

Signature:

```python
def record_eval_run(
    self,
    *,
    skill_version_id: str,
    eval_set_version_id: str,
    strategy: str,
    environment_tags: list[str],
    run_context: dict[str, Any],
    results: dict[str, Any],
    actor: str,
) -> RecordEvalRunResult:
```

Use helper:

```python
def normalize_run_context(environment_tags: list[str], run_context: dict[str, Any]) -> tuple[list[str], dict[str, Any], str]:
    normalized_tags = list(normalize_tags(environment_tags))
    normalized_context = dict(sorted(run_context.items()))
    payload = {"environment_tags": normalized_tags, "run_context": normalized_context}
    return normalized_tags, normalized_context, digest_text(json.dumps(payload, ensure_ascii=False, sort_keys=True))
```

Insert normalized tags/context/hash into `eval_runs`.

- [ ] **Step 6: Rework read models**

Change:

- `skill_detail` returns `versions`, `current_version`, `latest_eval_runs`; no `variants`.
- `list_skills` returns `current_version`; no `default_variant`.
- `eval_run_detail` returns `skill_version`; no `variant_version`.
- `list_eval_runs_for_skill` filters by `skill_version_id`, `eval_set_version_id`, `strategy`, `status`, and optional `run_context_hash`.
- `bundle_diff` accepts `left_skill_version_id` and `right_skill_version_id`.
- Remove `_variant_row`, `_variant_version_row`, `_variant_detail`, `_promotion_review`, and promotion methods.

- [ ] **Step 7: Permission rename**

In `permissions.py`, replace `variant.promote` with `skill_version.promote`. Keep `verification.accept`.

- [ ] **Step 8: Run repository/API tests**

Run:

```bash
cd apps/api
uv run pytest tests/test_sql_repository.py tests/test_api_commands.py tests/test_domain_invariants.py -q
```

Expected: PASS after repository and API updates in Task 5.

---

### Task 5: FastAPI Contract Implementation

**Files:**
- Modify: `apps/api/skillhub/api/main.py`
- Modify: `docs/api-contract.md`

- [ ] **Step 1: Replace payload classes**

Remove `ImportSkillPayload.tags`, `CreateVariantPayload`, `CreateVariantVersionPayload`, and `PromoteVariantVersionPayload`. Add:

```python
EnvironmentTagsPayload = Annotated[list[TagValue], Field(default_factory=list)]

class ImportSkillPayload(BaseModel):
    owner_ref: IdentityRef
    source: dict[str, Any]

class CreateSkillVersionPayload(BaseModel):
    skill_id: str
    content_ref: ContentRefPayload | None = None
    source: dict[str, Any] | None = None
    change_summary: VersionChangeSummary | None = None
    make_current: bool = False

class RecordEvalRunPayload(BaseModel):
    skill_version_id: str
    eval_set_version_id: str
    strategy: str = "manual_pass_fail"
    environment_tags: list[TagValue] = Field(default_factory=list)
    run_context: dict[str, Any] = Field(default_factory=dict)
    results: dict[str, bool | ManualEvalResultPayload]
```

- [ ] **Step 2: Replace routes**

Add:

```python
@app.post("/api/skill-versions")
def create_skill_version(...):
    ...
```

Remove:

- `POST /api/variants`
- `POST /api/variant-versions`
- `GET /api/variants/{variant_id}/promotion-review`
- `POST /api/variants/promotions`

- [ ] **Step 3: Change artifact diff query params**

Use:

```python
@app.get("/api/artifacts/diff")
def artifact_diff(left_skill_version_id: str, right_skill_version_id: str, repository: SqlSkillRepository = Depends(repository_dependency)):
    return result_payload(repository.bundle_diff(left_skill_version_id=left_skill_version_id, right_skill_version_id=right_skill_version_id))
```

- [ ] **Step 4: Update import flow**

`POST /api/skill-imports` calls `repository.create_skill(slug, owner_ref, content_ref, change_summary, actor)`.

Response includes:

```python
{
    **asdict(result),
    "slug": bundle.slug,
    "description": bundle.description,
    "file_count": bundle.file_count,
    "entry_path": bundle.entry_path,
    "bundle_artifact_id": artifact["id"],
    "bundle_digest": bundle.digest,
}
```

- [ ] **Step 5: Run API tests**

Run:

```bash
cd apps/api
uv run pytest -q
```

Expected: PASS.

---

### Task 6: Web Types, API Client, and Navigation

**Files:**
- Modify: `apps/web-v4/src/types.ts`
- Modify: `apps/web-v4/src/lib/api.ts`
- Modify: `apps/web-v4/src/lib/format.ts`
- Modify: `apps/web-v4/src/lib/navigation.ts`
- Modify: `apps/web-v4/src/components/Tabs.tsx`
- Rename or replace: `apps/web-v4/src/pages/VariantsPage.tsx`
- Rename or replace: `apps/web-v4/src/components/VariantInspector.tsx`
- Rename or replace: `apps/web-v4/src/components/VariantVersionTrack.tsx`

- [ ] **Step 1: Update types**

Replace `VariantVersion` with:

```ts
export type SkillVersion = {
  id: string;
  skill_id: string;
  version_number: number;
  content_ref: ContentRef;
  content_digest: string;
  change_summary: string;
  created_at?: string;
  created_by: string;
  bundle_files?: BundleFile[];
};
```

Change `SkillSummary` and `SkillDetail`:

```ts
export type SkillSummary = {
  skill: SkillRecord;
  current_version: SkillVersion | null;
  primary_eval_set: EvalSetSummary | null;
  latest_accepted_eval_run: EvalRunRecord | null;
};

export type SkillDetail = {
  skill: SkillRecord;
  summary: SkillSummary;
  versions: SkillVersion[];
  eval_sets: EvalSetSummary[];
  latest_eval_runs: EvalRunRecord[];
  role_assignments: unknown[];
  audit_events: unknown[];
};
```

- [ ] **Step 2: Update API client**

Use:

```ts
getBundleDiff: (leftSkillVersionId: string, rightSkillVersionId: string) =>
  apiGet<BundleDiff>(`/api/artifacts/diff?left_skill_version_id=${encodeURIComponent(leftSkillVersionId)}&right_skill_version_id=${encodeURIComponent(rightSkillVersionId)}`),
importSkill: (payload: { owner_ref: string; source: BundleSource }) =>
  apiSend<{ skill_id: string; skill_version_id: string }>("/api/skill-imports", "POST", payload),
createSkillVersion: (payload: { skill_id: string; source: BundleSource; make_current?: boolean }) =>
  apiSend<unknown>("/api/skill-versions", "POST", payload),
recordEvalRun: (payload: {
  skill_version_id: string;
  eval_set_version_id: string;
  strategy: string;
  environment_tags: string[];
  run_context: Record<string, string>;
  results: Record<string, ManualEvalResultPayload>;
}) => apiSend<{ eval_run_id: string }>("/api/eval-runs", "POST", payload),
```

- [ ] **Step 3: Rename route tab**

Change `SkillTab` from `"variants"` to `"versions"` and label it `版本`.

- [ ] **Step 4: Replace version UI**

Create `VersionsPage` from the old `VariantsPage` behavior:

- Header: `版本`
- Description: `SkillVersion 是不可变的 Skill bundle 快照。`
- No tag filters.
- Main area lists `skill.versions`.
- Upload panel calls `api.createSkillVersion`.
- Inspector shows current version, version track, bundle file list, backend diff, and details.

- [ ] **Step 5: Run TypeScript build**

Run:

```bash
cd apps/web-v4
npm run build
```

Expected: PASS after Task 7 updates page usage.

---

### Task 7: Web Forms, Eval Run Context, History, and E2E

**Files:**
- Modify: `apps/web-v4/src/pages/NewSkillModal.tsx`
- Modify: `apps/web-v4/src/pages/SkillPage.tsx`
- Modify: `apps/web-v4/src/pages/OverviewPage.tsx`
- Modify: `apps/web-v4/src/pages/EvaluatePage.tsx`
- Modify: `apps/web-v4/src/components/ManualVersionDetailPanel.tsx`
- Modify: `apps/web-v4/src/pages/HistoryPage.tsx`
- Modify: `apps/web-v4/e2e/helpers.ts`
- Modify: `apps/web-v4/e2e/formal-flow.spec.ts`
- Modify: `apps/web-v4/e2e/visual-seed.ts`
- Modify: `apps/web-v4/e2e/responsive-smoke.spec.ts`
- Modify: `apps/web-v4/e2e/visual-smoke.spec.ts`

- [ ] **Step 1: Remove tags from new skill**

`NewSkillModal` no longer renders `TagInput`. Submit:

```ts
const created = await api.importSkill({ owner_ref: actor, source });
```

Button disabled only when busy or no files.

- [ ] **Step 2: Add EvalRun environment inputs**

In `EvaluatePage`, add state:

```ts
const [environmentTags, setEnvironmentTags] = useState<string[]>([]);
const [runner, setRunner] = useState("");
const [model, setModel] = useState("");
const [operatingSystem, setOperatingSystem] = useState("");
```

Submit:

```ts
environment_tags: environmentTags,
run_context: Object.fromEntries(
  Object.entries({ runner, model, os: operatingSystem }).filter(([, value]) => value.trim())
),
```

- [ ] **Step 3: Update history cards**

Show:

- `SkillVersion vN`
- `EvalSetVersion vN`
- `运行环境` tags
- `run_context` key/value chips
- actual vs expected evidence

- [ ] **Step 4: Update E2E formal flow**

The flow should:

1. Create Skill without tags.
2. Upload SkillVersion v2.
3. Open `版本` tab and click Bundle diff.
4. Add/edit case.
5. On `测评`, select SkillVersion v2, enter `codex` and `windows` environment tags, fill actual output, record.
6. On `历史`, assert `codex`, `windows`, actual output, and expected output are visible.

- [ ] **Step 5: Run Web checks**

Run:

```bash
cd apps/web-v4
npm run test
npm run lint
npm run build
npm run e2e
```

Expected: PASS.

---

### Task 8: Documentation, Cleanup, and Full Verification

**Files:**
- Modify: `README.md`
- Modify: `docs/api-contract.md`
- Modify: `docs/formal-architecture-v0.1.md`
- Create: `docs/formal-web-v4-remove-variants-audit-2026-05-26.md`
- Modify: `apps/web-v4/e2e/formal-flow.md`
- Modify: `apps/web-v4/e2e/visual-smoke.md`

- [ ] **Step 1: Update README**

Replace core model bullets with:

```markdown
- `SkillVersion` 是不可变 Skill bundle 内容快照。
- `EvalRun` 记录一次 exact `SkillVersion + EvalSetVersion + run_context` 的结果。
- 运行环境标签只属于 EvalRun，例如 runner、model、OS 或 sandbox。
```

- [ ] **Step 2: Update formal architecture and API contract**

Remove Variant sections and endpoints. Add SkillVersion fields and endpoints from the design spec.

- [ ] **Step 3: Add audit document**

Document:

- Why Variant was removed.
- What fields moved to EvalRun.
- Migration behavior.
- Verification commands and agent-browser smoke.

- [ ] **Step 4: Full verification**

Run:

```bash
cd apps/api
uv run pytest
```

```bash
cd apps/web-v4
npm run test
npm run lint
npm run build
npm run e2e
npm run e2e:visual
```

```bash
git diff --check
```

- [ ] **Step 5: Agent-browser smoke**

Start:

```bash
SKILLHUB_API_PORT=18141 SKILLHUB_WEB_PORT=13141 SKILLHUB_DATA_DIR=/private/tmp/skillhub-devariant-smoke-data bash scripts/dev.sh
```

Use agent-browser to verify:

- `/skills` loads.
- Create or seed a Skill.
- `/skills?skill=<id>&tab=versions` shows `版本`, not `变体`.
- Bundle diff shows backend data.
- Eval run records environment tags and actual output.
- History still shows the run after service restart.
- 320px viewport has no document/body horizontal overflow.

- [ ] **Step 6: Commit, push, PR, CI**

Commit remaining changes:

```bash
git status --short
git add -A
git commit -m "refactor: remove variants from skillhub core model"
git push -u origin refactor/remove-variants-run-context
gh pr create --base main --head refactor/remove-variants-run-context --title "[codex] Remove variants from SkillHub core model" --body-file /tmp/remove-variants-pr.md
gh pr checks --watch --interval 10
```

Merge only after checks pass.

---

## Self-Review

- Spec coverage: Tasks cover schema, migration, repository, API, Web UI, E2E, docs, full verification, agent-browser, push, and CI.
- Open-item scan: No unfinished plan items. Later optional `skill_version_decisions` is explicitly out of scope in the design and not part of this implementation plan.
- Type consistency: Plan consistently uses `SkillVersion`, `skill_version_id`, `environment_tags`, `run_context`, and `run_context_hash`.
