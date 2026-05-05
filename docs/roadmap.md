# SkillHub Demo Roadmap

This document captures the current demo boundary and the next steps toward a formal product.

## Current State

The demo now proves the core loop:

- Hub lists skills.
- `Skill` points to a default `Variant`.
- `Variant` points to a current immutable `VariantVersion`.
- `VariantVersion.content_ref` points to skill content.
- `EvalSetVersion` snapshots eval case membership and order.
- `EvalRun` records pass/fail results for one `VariantVersion + EvalSetVersion`.
- Case-level results are visible from eval result pages.
- Skill bundle content can be imported, viewed, and diffed.
- Archive/deprecate exists for Skill and Variant without hard delete.

## Backend Boundary

Current shape:

```text
HTTP API
  -> Repository
    -> SkillHubStore domain rules
    -> SQLite app_state snapshot
    -> SQLite normalized read tables
    -> ArtifactStore bundle content
```

Important properties:

- Domain facts remain append-friendly.
- The default runtime store is SQLite.
- JSON mode remains available for disposable local experiments.
- Core read paths use SQL read models.
- Write paths go through Repository mutation.
- Skill bundle content is behind `ArtifactStore`.
- GitHub Actions runs backend tests and frontend build on push and PR.

## Closed MVP Items

- Multi-skill flow.
- Variant creation.
- Variant version publishing.
- Eval case creation.
- Eval set versioning.
- Manual pass/fail eval runs.
- Result detail by case.
- Skill bundle import and detail view.
- Bundle diff from immutable snapshots.
- SQLite persistence.
- SQL read models for hub, skill, variant, eval set, and eval result.
- Archive/restore controls for Skill and Variant in the demo UI.
- Minimal CI.

## Intentional Gaps

These are not bugs in the demo; they are product decisions deferred until the model is stable:

- Multi-user auth and permissions.
- Fork / PR collaboration flow.
- Automatic eval execution.
- LLM judge / rubric strategies.
- Upgrade agent / optimizer strategies.
- Rich multidimensional table views.
- Production UI design.
- Real Git adapter.
- Real object storage adapter.
- Formal migrations beyond the first v2 schema migration.

## Next Implementation Order

1. Adapter hardening

   Define concrete `GitArtifactStore` and `ObjectArtifactStore` contracts, but keep the current file-backed store as the default local mode.

2. Eval strategy plugins

   Add a strategy registry around eval execution. Manual pass/fail remains one strategy; future strategies can call scripts, external tools, LLM judges, or human review queues.

3. Upgrade experiment model

   Introduce an `Experiment` or `UpgradeAttempt` object to record proposed content changes, eval before/after, and final promotion decision.

4. Permission model

   Add owners, roles, and publish/archive permissions before fork/PR collaboration.

5. Formal frontend rebuild

   Rebuild the UI around the proven information architecture: hub, variant page, eval set detail, eval result detail, and management console.

## Product Thesis

The platform should not compete with GitHub as a generic code host. It should use Git-like ideas where they help, but its main value is eval-backed skill reliability:

- content is versioned,
- variants represent best-known answers under constraints,
- eval set versions make progress measurable,
- every promotion can be checked against previous expectations,
- bad cases become durable eval cases instead of anecdotes.

Distribution is only the visible tip. The real product is the reliability layer under every published skill.
