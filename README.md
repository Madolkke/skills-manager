# Skills Manager

Eval-backed SkillHub prototype for managing skill variants, versioned eval sets, manual eval runs, and standard skill bundle snapshots.

## What This Demo Proves

- A `Skill` is a stable hub entry.
- A `Variant` is the maintained best answer for a tag constraint set.
- A `VariantVersion` is an immutable content snapshot.
- An `EvalSetVersion` is a case snapshot.
- An `EvalRun` records pass/fail results for one `VariantVersion + EvalSetVersion`.
- Standard skill folders can be imported as `skill_bundle` artifacts and viewed or diffed by version.

## Run The Frontend

```bash
cd demo
npm install
npm run dev
```

Open `http://127.0.0.1:5173`.

## Run The Backend

Use a virtual environment so the demo does not touch the global Python install:

```bash
cd demo-backend
python3 -m venv .venv
. .venv/bin/activate
python -m unittest discover -s tests
python -m skillhub_demo.server --port 8788
```

The backend uses only the Python standard library and persists demo state to `demo-backend/data/skillhub-demo.json`.

## Main Docs

- [MVP spec](docs/MVP_SPEC.md)
- [API contract](docs/api-contract.md)
- [Design spec](docs/mvp-design-spec.md)
