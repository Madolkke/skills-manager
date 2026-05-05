# Storage Adapter Contract

This document sketches the storage adapter boundary for skill bundle content. The current demo has a file-backed `ArtifactStore`; future adapters can target Git, object storage, or hybrid storage without changing the core Skill / Variant / Eval model.

## Current Boundary

Domain state stores only:

- `Artifact.id`
- `Artifact.kind`
- `Artifact.content_hash`
- `Artifact.media_type`
- `Artifact.content` as a locator
- `VariantVersion.content_ref`

The actual skill bundle bytes live behind `ArtifactStore`.

Current implementation:

```text
HTTP
  -> Repository
    -> SkillHubStore for domain rules
    -> SQLite / JSON for state
    -> ArtifactStore for bundle content
```

## Minimal Interface

The stable interface should stay small:

```python
class ArtifactStore(Protocol):
    label: str

    def write_text(self, namespace: str, content_hash: str, content: str) -> str:
        ...

    def read_text(self, locator: str) -> str:
        ...
```

Required semantics:

- `write_text` is content-addressed and idempotent.
- `content_hash` is computed before writing.
- returned `locator` is immutable.
- `read_text(locator)` returns the exact bytes represented by the hash.
- path traversal and ambiguous locator formats are rejected.

## Git Adapter Draft

Git is useful when we want native file diff, history, branch, PR, fork, and review workflows.

Proposed locator:

```text
git:<remote-or-local-repo>#<commit-sha>:<path>
```

Example:

```text
git:skills-content.git#abc1234:bundles/code-reviewer/
```

Adapter responsibilities:

- materialize a normalized skill folder into a Git tree.
- create a commit for each immutable bundle snapshot.
- return a locator containing commit SHA and bundle path.
- read bundle content at an exact commit, never from a moving branch.
- expose optional diff helpers later, but keep `ArtifactStore` minimal.

Do not use Git branch names as immutable content locators. Branches are collaboration pointers; `VariantVersion.content_ref` must point to immutable content.

## Object Storage Adapter Draft

Object storage is useful for simple immutable blobs and large assets.

Proposed locator:

```text
object:<bucket>/<key>#<sha256>
```

Example:

```text
object:skillhub-artifacts/skill-bundles/4f9a...json#4f9a...
```

Adapter responsibilities:

- write content under a content-addressed key.
- verify returned object hash / etag where possible.
- read by exact object key and verify digest.
- support later migration to CDN or signed URLs.

## Hybrid Strategy

A pragmatic formal version can use both:

- Git adapter for human-editable skill folders and PR review.
- Object storage for large generated assets, reports, logs, and binary attachments.
- Database stores only locator, digest, media type, and ownership metadata.

This keeps the platform model stable while allowing content storage to evolve.

## Open Decisions

- Whether skill bundle snapshots should be stored as one normalized JSON object or as a real folder tree.
- Whether Git commits are created by the platform or imported from user-owned repos.
- Whether object storage should be local-first for single-user deployments.
- How to authorize reads/writes once multi-user permissions exist.
