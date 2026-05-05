# SkillHub 1.0 Architecture Review

This document turns the demo findings into a first production-oriented architecture. It is intentionally opinionated, but still lightweight enough to revise before implementation.

## Goal

Build a SkillHub that distributes skills and proves reliability through versioned eval evidence.

The core product promise:

- users can find a skill like a normal hub,
- every published skill entry points to a maintained variant,
- every variant points to immutable content versions,
- every meaningful update can be evaluated against a versioned eval set,
- platform storage can evolve without changing the Skill / Variant / Eval model.

## Non-Goals For 1.0

- Do not build a full GitHub replacement.
- Do not make auto-optimization the default path.
- Do not require one universal eval method.
- Do not over-design variant lineage or parent/child graphs before fork/PR exists.
- Do not rebuild the demo UI as the production UI; keep the demo as a model probe.

## Core Domain Model

### Skill

A stable discovery entry.

Fields:

- `id`: stable identifier.
- `name`: display name.
- `summary`: what this skill does.
- `default_variant_id`: pointer to the variant users get by default.
- `status`: active, archived.
- `created_at`, `updated_at`: audit timestamps.

Rule:

- Skill does not own content directly. It points to a variant.

### Variant

The maintained best answer for a set of constraints, expressed as tags.

Fields:

- `id`: stable identifier.
- `skill_id`: owning skill.
- `tags`: constraint tags, for example `codex`, `gpt5.4`, `opencode`, `minimax2.7`.
- `current_version_id`: pointer to the current immutable version.
- `status`: active, archived.
- `created_at`, `updated_at`: audit timestamps.

Rules:

- Variant identity is human-maintained. It is not dynamically computed from evals.
- Tags describe the situation where this variant is considered the best maintained answer.
- Variant history is its own ordered list of versions.
- A variant does not need a parent unless fork/PR collaboration is introduced later.

### VariantVersion

An immutable content snapshot.

Fields:

- `id`: stable identifier.
- `variant_id`: owning variant.
- `version_number`: monotonic number inside the variant.
- `content_ref`: immutable artifact locator.
- `content_hash`: digest of normalized content.
- `change_summary`: short commit-like explanation.
- `created_at`: timestamp.
- `created_by`: actor reference once auth exists.

Rules:

- Never mutate a version.
- Creating a new version does not automatically make it current unless the publish command says so.
- Promotion means updating `Variant.current_version_id` to an existing immutable version.
- A candidate is still a real `VariantVersion`; it is simply not the version currently referenced by `Variant.current_version_id`.
- Diff is computed between immutable content refs, not from mutable variant state.

### EvalSet

A named evaluation suite for a skill.

Fields:

- `id`: stable identifier.
- `skill_id`: owning skill.
- `name`: display name.
- `description`: what quality this suite measures.
- `current_version_id`: latest eval set version.
- `status`: active, archived.

Rule:

- Variants of the same skill can share eval sets, because they are competing answers to the same user need under different constraints.

### EvalSetVersion

An immutable case snapshot.

Fields:

- `id`: stable identifier.
- `eval_set_id`: owning eval set.
- `version_number`: monotonic number.
- `case_version_ids`: ordered `EvalCaseVersion` snapshot.
- `case_snapshot_ref`: immutable artifact locator for full case content, if case content is stored outside the database.
- `created_at`: timestamp.

Rules:

- Case content can change only by creating a new `EvalCaseVersion`.
- Eval set membership or ordering can change only by creating a new `EvalSetVersion`.
- Eval result pages must show the exact cases used by that run.

### EvalCase

A stable test scenario entry.

Fields:

- `id`: stable identifier.
- `skill_id`: owning skill.
- `title`: short scenario name.
- `current_version_id`: pointer to the latest maintained case version.
- `status`: active, archived.

Rule:

- `EvalCase` does not contain mutable test content directly. It points to `EvalCaseVersion`.

### EvalCaseVersion

An immutable snapshot of a test example.

Fields:

- `id`: stable identifier.
- `case_id`: owning eval case.
- `version_number`: monotonic number inside the case.
- `input_ref`: task input artifact or inline content.
- `expected_output_ref`: expected behavior or answer artifact or inline content.
- `notes`: optional human context.
- `created_at`: timestamp.

Rules:

- Never mutate a case version.
- Fixing input, expected output, or notes creates a new `EvalCaseVersion`.
- A case is not a checklist. For the demo-level manual strategy, one case result is only pass or fail.

### EvalRun

A result for one variant version against one eval set version.

Fields:

- `id`: stable identifier.
- `variant_version_id`: exact evaluated content.
- `eval_set_version_id`: exact evaluated case set.
- `strategy`: manual, script, external, llm_judge, human_queue, etc.
- `summary`: pass count, fail count, score.
- `case_results`: pass/fail result for each case in the eval set version.
- `created_at`: timestamp.
- `created_by`: actor reference once auth exists.

Rules:

- EvalRun is evidence, not truth by itself.
- Different strategies can coexist if the result schema is normalized.
- The platform can record results from user-provided methods before it runs them itself.

## Permission And Collaboration Model

Start simple, but leave the shape open for fork/PR.

### 1.0 Roles

- Owner: can archive, restore, publish, and manage permissions.
- Maintainer: can create variants, publish versions, update eval sets, and run evals.
- Evaluator: can submit eval runs and case results.
- Viewer: can read public or shared skills.

### Role Assignment Scope

Roles are scoped grants, not global labels:

```text
subject + resource_type + resource_id + role
```

Examples:

- user A is `maintainer` on skill `code-reviewer`.
- user B is `evaluator` on eval set `code-reviewer-regression`.
- org C is `owner` on a content namespace.

Resource scopes should inherit conservatively:

- skill-level roles apply to variants, versions, eval sets, and eval cases under that skill.
- variant-level roles apply only to that variant and its versions.
- content namespace roles control artifact reads and writes.

### Write Boundaries

- Publishing a new `VariantVersion` requires write access to that variant.
- Changing `Skill.default_variant_id` requires maintainer or owner access.
- Creating `EvalSetVersion` requires maintainer access.
- Recording `EvalRun` requires evaluator access.
- Archive/restore requires maintainer access; hard delete should remain admin-only or unavailable.

### Later Fork/PR Shape

Fork/PR should be modeled as collaboration around proposed versions, not as variant lineage.

Proposed future objects:

- `Fork`: user's writable copy of a skill or variant.
- `ChangeProposal`: proposed `VariantVersion` plus eval evidence.
- `Review`: approval, requested changes, or rejection.

This keeps variant semantics clean: a variant is still the maintained best answer for tags, not a historical branch graph.

## Storage Architecture

Keep metadata in the database and content behind an artifact adapter.

```text
HTTP API
  -> Application service
    -> Domain repository
      -> SQL metadata store
      -> ArtifactStore
```

### Database Owns

- identities,
- relationships,
- permissions,
- status,
- current pointers,
- eval summaries,
- query indexes.

### ArtifactStore Owns

- skill bundle content,
- normalized case snapshots when needed,
- large eval logs,
- generated reports,
- binary attachments.

### Recommended 1.0 Storage

- SQL database for metadata and read models.
- Git-backed adapter for human-editable skill folders stored as normalized file trees.
- Object storage adapter for large reports, logs, and binary assets.
- Local file-backed adapter remains the development mode.
- Single JSON blob storage is allowed only as a demo or compatibility fallback.

This is close to GitHub's practical split: Git stores repository content and history; databases store users, permissions, issues, PRs, search indexes, checks, and product metadata.

## API Shape

Stable top-level resources:

- `/api/skills`
- `/api/skills/{skill_id}`
- `/api/skills/{skill_id}/variants`
- `/api/variants/{variant_id}`
- `/api/variants/{variant_id}/versions`
- `/api/eval-sets`
- `/api/eval-sets/{eval_set_id}/versions`
- `/api/eval-runs`
- `/api/artifacts/{artifact_id}`

Important API rule:

- Read endpoints should return denormalized view data.
- Write endpoints should accept narrow commands.

This avoids forcing the frontend to reconstruct product concepts from low-level rows.

## Frontend Information Architecture

Production UI should use the demo's model, not its layout.

### Hub Page

Purpose:

- browse and search skills like a normal skillhub.

Shows:

- skill name,
- summary,
- default variant tags,
- verification summary,
- status.

`verification summary` must be explicit:

- default variant current version,
- primary eval set current version,
- latest accepted run,
- strategy,
- timestamp,
- pass/fail counts and score.

The UI may render this compactly, for example `8/10 passed · manual · eval v4`, but the backing data should not be a vague "latest score".

### Skill / Variant Page

Purpose:

- show one maintained answer.

Shows:

- what the skill does,
- current variant tags,
- current version,
- content preview,
- eval overview,
- linked eval set versions,
- history versions,
- sibling variants as a map or table.

Rule:

- Clicking a variant opens the same page shape, because a skill entry resolves to a variant.

### Eval Set Version Page

Purpose:

- inspect exact cases.

Shows:

- version metadata,
- ordered cases,
- each case input and expected output,
- which eval runs used this version.

### Eval Run Page

Purpose:

- inspect evidence.

Shows:

- evaluated variant version,
- evaluated eval set version,
- strategy,
- pass/fail summary,
- case-level results.

### Management Console

Purpose:

- create and update operational objects.

Shows:

- create skill,
- create variant,
- publish version,
- add eval case,
- create eval set version,
- run manual eval,
- archive/restore.

## Eval Strategy Architecture

The platform should record final normalized results first, then gradually execute strategies itself.

```text
EvalStrategy
  -> input: VariantVersion + EvalSetVersion
  -> output: EvalRunDraft
  -> persisted as EvalRun
```

Initial strategies:

- `manual_pass_fail`: human records pass/fail per case.
- `external_result_import`: user imports a result file matching the contract.

Later strategies:

- `script_runner`: runs user-provided scripts.
- `llm_judge`: model-based rubric scoring.
- `human_review_queue`: tasks that require interactive judgment.
- `upgrade_agent`: proposes a new version, then asks eval strategies for evidence.

## Upgrade Flow

Do not make upgrade a magic button at first. Make it evidence-backed.

1. Create candidate content.
2. Store it as an artifact.
3. Create a new immutable `VariantVersion` that points to that artifact.
4. Run or import evals against selected eval set versions.
5. Compare current version evidence with candidate version evidence.
6. Maintainer promotes the candidate by moving `Variant.current_version_id` to that existing version.

Future automation can compress these steps, but the record should stay explicit.

## Implementation Order

1. Stabilize backend API contracts.
2. Replace demo in-memory/domain snapshot seams with explicit application services.
3. Introduce auth and roles.
4. Implement storage adapter interface with file-backed default and Git-backed prototype.
5. Add external eval result import.
6. Add production frontend IA with hub, variant page, eval set version page, eval run page, and management console.
7. Add fork/proposal only after permissions and immutable versions are stable.

## Key Design Decisions

- Use Git ideas, but do not make Git the product model.
- Treat variant as a maintained pointer for tag constraints.
- Treat version as immutable truth.
- Treat non-current candidate content as a normal immutable version, not a separate draft object.
- Treat eval cases the same way: stable case entries point to immutable case versions.
- Treat eval run as evidence tied to exact variant and eval set versions.
- Treat storage as replaceable infrastructure.
- Keep bad cases as future eval cases, not as a separate primary object.
