# SkillHub Product Completion Audit

Date: 2026-05-08

Status: not complete. The current product has a stronger runnable vertical slice with bundle diff now implemented, but several explicit maturity requirements remain before calling it mature.

## Objective Restated As Success Criteria

The project should become a mature SkillHub product, not just a prototype. Concretely:

1. One-command local startup without polluting the global Python environment.
2. A polished frontend informed by strong product patterns, with good layout, typography, color, responsive behavior, and smooth user operation.
3. Standard skill folder and zip import.
4. Skill and variant creation/edit/archive flows.
5. Eval case create/edit/archive flows.
6. Manual experiment flow where each case is marked pass/fail and persisted as an exact eval run.
7. Versioned model correctness: `Skill -> Variant -> VariantVersion`, shared versioned eval sets, exact `VariantVersion + EvalSetVersion` binding.
8. More mature operations beyond the minimum, especially artifact/file visibility, version history, bundle diff, run history, and case history.
9. README and docs that explain how to run and verify the product.
10. Regression coverage proving the user flows and visual quality do not silently regress.
11. Before major UX changes, research strong existing products, adapt their ideas, document the reasoning, then implement.

## Prompt-To-Artifact Checklist

| Requirement | Current evidence | Status |
| --- | --- | --- |
| One-command startup | `scripts/dev.sh` starts FastAPI and Next.js, creates `.data`, uses `uv`, installs web dependencies if missing; README documents `bash scripts/dev.sh`. | Complete for local dev |
| Avoid global Python pollution | `scripts/dev.sh` uses `uv run`; README explicitly says it does not write to global Python environment. | Complete |
| Standard folder import | `POST /api/skill-imports`; E2E `operator can import a skill...`; API test `test_import_skill_from_file_tree_uses_skill_md_frontmatter`. | Complete |
| Standard zip import | E2E `operator can import a zipped standard skill bundle`; API test `test_import_skill_from_zip_uses_same_bundle_contract`. | Complete |
| New skill flow | `POST /api/skills`; inspector `new-skill`; E2E keyboard opens `新建 skill`. | Mostly complete |
| New variant flow | `POST /api/variants`; E2E creates `Strict reviewer`. | Complete |
| Variant version flow | `POST /api/variant-versions`; backend tests cover current pointer behavior and candidate evaluation. Frontend `追加版本` accepts standard folders/zips and has E2E coverage. | Complete for standard bundle versions |
| Eval case create | `POST /api/eval-cases`; E2E `addEvalCase`. | Complete |
| Eval case edit/versioning | `PATCH /api/eval-cases/{case_id}`; E2E `operator can edit and archive eval cases`; backend tests verify new eval set snapshots. | Complete |
| Eval case archive | `DELETE /api/eval-cases/{case_id}`; E2E archives a case. | Complete |
| Manual pass/fail eval | E2E marks one case `通过` and records an eval run; backend tests record pass/fail exact versions. | Complete for manual MVP |
| Exact version binding | Backend schema/tests enforce same-skill `VariantVersion + EvalSetVersion`; domain tests cover candidate version eval before promotion and cross-skill rejection. | Complete |
| Active hub hides archived skill | Repository `list_skills` filters `lifecycle_status == active`; API command test checks archived skill no longer appears. | Complete |
| Skill bundle file content visible | Workbench shows bundle file list and `SKILL.md`; visual snapshots include imported overview. | Complete for current bundle preview |
| Bundle version diff | `GET /api/artifacts/diff`; backend tests cover changed/added/removed, binary, and cross-skill rejection. Workbench `比较版本` shows file rail and line diff; E2E covers imported skill with two bundle versions. | Complete for current/previous bundle review |
| Run history table/filtering | Listed in `docs/product-ux-review.md` next queue; no UI table/query yet. | Missing |
| Inline case version history | Backend model supports versions; product review flags inline history as missing. | Missing in UI |
| Mature frontend | `/skills` is a tri-pane workbench with visual regression snapshots; product review documents Linear/GitHub/Claude-inspired patterns. | Good but not complete |
| Visual regression | `apps/web/e2e/visual-workbench.spec.ts` covers empty, imported overview, manual eval, mobile empty snapshots. | Complete baseline |
| Accessibility depth | Keyboard activation test exists; product review flags richer accessibility assertions as missing. | Partial |
| README run/verify docs | README includes one-command run, manual run, product flow, verification commands, docs links. | Complete |
| Research before UX changes | Formal workbench spec and bundle diff spec cite/adapt GitHub, VS Code, Linear, Claude Skills-style contract. | Complete for current changes |
| Every push runnable | Latest pushed commits were verified before push; this audit should be refreshed after the current bundle diff branch completes full verification. | Pending current verification |

## Actual Verification Assets

Frontend E2E:

- `apps/web/e2e/skills-workbench.spec.ts`
  - invalid folder import blocks submission.
  - folder import, new variant, new case, manual eval run.
  - zipped standard bundle import.
  - keyboard access to primary inspector actions.
  - edit and archive eval cases.
  - compare two standard bundle versions and inspect file-level diff.
  - mobile viewport width.
- `apps/web/e2e/visual-workbench.spec.ts`
  - empty workbench screenshot.
  - imported skill overview screenshot.
  - manual eval review screenshot.
  - mobile empty workbench screenshot.

Backend tests:

- `apps/api/tests/test_api_commands.py`
- `apps/api/tests/test_api_persistence.py`
- `apps/api/tests/test_domain_invariants.py`
- `apps/api/tests/test_schema_contract.py`
- `apps/api/tests/test_sql_repository.py`
- `apps/api/tests/test_sqlalchemy_metadata.py`

Key API surface currently present:

- `GET /health`
- `GET /api/skills`
- `GET /api/skills/{skill_id}`
- `GET /api/eval-set-versions/{eval_set_version_id}`
- `GET /api/eval-runs/{eval_run_id}`
- `GET /api/artifacts/diff`
- `POST /api/skills`
- `POST /api/skill-imports`
- `POST /api/variant-versions`
- `POST /api/variants`
- `POST /api/variants/promotions`
- `PATCH /api/skills/{skill_id}`
- `DELETE /api/skills/{skill_id}`
- `POST /api/eval-cases`
- `POST /api/eval-case-versions`
- `PATCH /api/eval-cases/{case_id}`
- `DELETE /api/eval-cases/{case_id}`
- `POST /api/eval-runs`

## Gaps Blocking "Mature Product" Completion

1. **Run history is not queryable.** Users can record eval runs, but cannot efficiently filter or compare historical runs.
2. **Case version history is not visible inline.** The backend is rigorous, but the UI does not expose the full case history clearly.
3. **Inspector flow is still form-first.** It is cleaner than before, but repeated operations should become more guided and less verbose.
4. **Diff scope is file-review only.** The workbench compares two bundle artifacts, but does not yet connect diff hunks to eval impact or promotion decisions.
5. **Accessibility coverage is shallow.** Keyboard smoke exists, but no deeper focus-order, label, or reduced-motion assertions.
6. **Zip preview waits for backend validation.** Folder preview is richer than zip preview.

## Next Concrete Step

Do not mark the goal complete.

The next implementation step should be run and case history:

1. Add a run history read model with filters for variant version, eval set version, result, strategy, and date.
2. Expose inline case version history from each case row.
3. Connect version diff, eval result, and promotion decision in one review surface.
4. Add E2E coverage for historical run lookup and case version restore/read-only review.

Until that ships, the product should be described as a strong formal vertical slice, not a completed mature SkillHub.
