# SkillHub Product UX Review

Last updated: 2026-05-08

## Current Working Flow

- `/skills` is a polished tri-pane workbench: catalog, focused workspace, contextual inspector. The main interaction model now follows a Linear-style selected-object workspace rather than a page of stacked forms.
- Users can create a skill, import a standard skill folder or zip, create variants, add/edit/archive eval cases, and record manual pass/fail eval runs.
- The API persists local data to `.data/skillhub.sqlite3` through `scripts/dev.sh`.
- Empty databases show a real first-run state with import/new-skill actions instead of pretending sample data is persisted workspace data.
- Archived skills are still addressable by id for audit/history, but they no longer appear in the active SkillHub list.
- Manual eval runs require every case to be explicitly marked pass or fail before submission.
- Standard bundle versions can be compared in a dedicated diff mode with version selectors, file status filters, a changed-file rail, and line-level text diff.
- Playwright browser tests cover invalid folder import, zipped bundle import, the critical happy path, keyboard activation for primary inspector actions, edit/archive case management, bundle version diff, a mobile viewport width check, and visual screenshot regression for empty, imported overview, manual eval, and mobile states.

## Borrowed Product Patterns

- Linear-style workspace density: one selected object, a compact left catalog, and a right inspector for contextual operations.
- GitHub-style import affordance: a bundle import has an explicit source, validates the contract, creates a versioned immutable artifact, and exposes bundle files through the read model.
- GitHub/VS Code-style diff review: compare two immutable bundle snapshots through a file rail plus line-oriented additions/removals rather than hiding changes inside a metadata form.
- Claude Skills-style bundle contract: `SKILL.md` is the required root entry, and frontmatter supplies the product-facing name and description.

## Friction Found

1. The right inspector is now cleaner, but still relies on forms rather than a fully guided wizard. Frequent actions can still become more compressed once real users repeat the flow.
2. Diff review is now first-class, but it does not yet show eval impact beside changed files.
3. Case editing creates a new case version, but the workbench does not yet show per-case version history inline.
4. Manual eval runs are explicit and safer, but the user cannot yet filter or compare historical runs in a table.
5. Import preview works for folders; zip preview still waits for backend validation because browser-side zip parsing is not implemented.
6. Browser interaction coverage now includes screenshot regression, but still lacks richer accessibility assertions.

## Next Optimization Queue

1. Add a guided case/eval flow: collapse advanced fields further, keep pass/fail confirmation central, and reduce inspector form density after real usage feedback.
2. Add inline eval case history: each case row should expose previous versions and the eval set versions that included them.
3. Add a run history table: filter by variant version, eval set version, result, strategy, and created date.
4. Connect bundle diff to eval impact: show which eval set/run should be reviewed before promotion.
5. Expand browser-level interaction tests with richer accessibility assertions and more run-history states.
