# SkillHub Product Completion Audit

Date: 2026-05-08

Status: not complete. The current product has a strong runnable vertical slice, but several explicit maturity requirements are still missing or only designed.

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
| Variant version flow | `POST /api/variant-versions`; backend tests cover current pointer behavior and candidate evaluation. Frontend has `追加版本` form. | Functional, weaker E2E coverage |
| Eval case create | `POST /api/eval-cases`; E2E `addEvalCase`. | Complete |
| Eval case edit/versioning | `PATCH /api/eval-cases/{case_id}`; E2E `operator can edit and archive eval cases`; backend tests verify new eval set snapshots. | Complete |
| Eval case archive | `DELETE /api/eval-cases/{case_id}`; E2E archives a case. | Complete |
| Manual pass/fail eval | E2E marks one case `通过` and records an eval run; backend tests record pass/fail exact versions. | Complete for manual MVP |
| Exact version binding | Backend schema/tests enforce same-skill `VariantVersion + EvalSetVersion`; domain tests cover candidate version eval before promotion and cross-skill rejection. | Complete |
| Active hub hides archived skill | Repository `list_skills` filters `lifecycle_status == active`; API command test checks archived skill no longer appears. | Complete |
| Skill bundle file content visible | Workbench shows bundle file list and `SKILL.md`; visual snapshots include imported overview. | Complete for current bundle preview |
| Bundle version diff | Design spec exists: `docs/superpowers/specs/2026-05-08-bundle-diff-workbench-design.md`; no API/UI implementation yet. | Missing |
| Run history table/filtering | Listed in `docs/product-ux-review.md` next queue; no UI table/query yet. | Missing |
| Inline case version history | Backend model supports versions; product review flags inline history as missing. | Missing in UI |
| Mature frontend | `/skills` is a tri-pane workbench with visual regression snapshots; product review documents Linear/GitHub/Claude-inspired patterns. | Good but not complete |
| Visual regression | `apps/web/e2e/visual-workbench.spec.ts` covers empty, imported overview, manual eval, mobile empty snapshots. | Complete baseline |
| Accessibility depth | Keyboard activation test exists; product review flags richer accessibility assertions as missing. | Partial |
| README run/verify docs | README includes one-command run, manual run, product flow, verification commands, docs links. | Complete |
| Research before UX changes | Formal workbench spec and bundle diff spec cite/adapt GitHub, VS Code, Linear, Claude Skills-style contract. | Complete for current changes |
| Every push runnable | Latest runtime-affecting commit `ab0e4f1` was verified with `npm run typecheck`, `npm run build`, `npm run e2e`, `uv run pytest`, `git diff --check`; latest commit `dff1cde` was docs-only and passed `git diff --check`. | Acceptable |

## Actual Verification Assets

Frontend E2E:

- `apps/web/e2e/skills-workbench.spec.ts`
  - invalid folder import blocks submission.
  - folder import, new variant, new case, manual eval run.
  - zipped standard bundle import.
  - keyboard access to primary inspector actions.
  - edit and archive eval cases.
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

1. **Bundle diff is not implemented.** This is now designed, but not coded. It is the next high-leverage step because the README already claims standard skill bundles can be diffed by version.
2. **Run history is not queryable.** Users can record eval runs, but cannot efficiently filter or compare historical runs.
3. **Case version history is not visible inline.** The backend is rigorous, but the UI does not expose the full case history clearly.
4. **Inspector flow is still form-first.** It is cleaner than before, but repeated operations should become more guided and less verbose.
5. **Accessibility coverage is shallow.** Keyboard smoke exists, but no deeper focus-order, label, or reduced-motion assertions.
6. **Zip preview waits for backend validation.** Folder preview is richer than zip preview.
7. **README wording overstates diff.** README says bundles can be viewed or diffed by version; after the design-only commit this is still not true in the product.

## Next Concrete Step

Do not mark the goal complete.

The next implementation step should be the approved Bundle Diff Workbench:

1. Add backend `GET /api/artifacts/diff?left_variant_version_id=&right_variant_version_id=`.
2. Add API tests for changed, added, removed, binary, cross-skill rejection, and missing bundle artifact.
3. Add frontend types and API client call.
4. Add `/skills` workbench diff mode or panel.
5. Add E2E and screenshot regression for an imported skill with two versions and visible file-level diff.
6. Update README only after the diff actually works.

Until that ships, the product should be described as a strong formal vertical slice, not a completed mature SkillHub.
