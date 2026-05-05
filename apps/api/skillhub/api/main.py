from __future__ import annotations

from fastapi import FastAPI


app = FastAPI(title="SkillHub API", version="0.1.0")


@app.get("/health")
def health() -> dict[str, bool]:
    return {"ok": True}
