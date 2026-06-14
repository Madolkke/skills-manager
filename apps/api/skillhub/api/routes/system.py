from __future__ import annotations

from fastapi import FastAPI


def register_system_routes(app: FastAPI) -> None:
    @app.get("/health")
    def health() -> dict[str, bool]:
        return {"ok": True}
