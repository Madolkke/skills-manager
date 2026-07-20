from __future__ import annotations

import hashlib
import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from skillhub.bootstrap.exceptions import register_exception_handlers
from skillhub.models.errors import ConflictError, FieldError, FieldInvariantError, NotFoundError, PermissionDeniedError
from skillhub.views import register_views

OPENAPI_SHA256 = "aeab7be163bf8e60ee8ee777302f1644ec4c81b47604de70c22e1e716fd7b023"


def test_openapi_contract_snapshot() -> None:
    app = FastAPI(title="SkillHub API", version="0.1.0")
    register_views(app)

    normalized = json.dumps(app.openapi(), ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()

    assert len(app.openapi()["paths"]) == 91
    assert hashlib.sha256(normalized).hexdigest() == OPENAPI_SHA256


def test_core_error_response_contracts() -> None:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/not-found")
    def not_found() -> None:
        raise NotFoundError("missing")

    @app.get("/invalid")
    def invalid() -> None:
        raise FieldInvariantError("invalid", [FieldError(field="status", message="already closed", code="invalid_state")])

    @app.get("/conflict")
    def conflict() -> None:
        raise ConflictError("conflict")

    @app.get("/denied")
    def denied() -> None:
        raise PermissionDeniedError("denied")

    client = TestClient(app)

    not_found_response = client.get("/not-found")
    invalid_response = client.get("/invalid")
    conflict_response = client.get("/conflict")
    denied_response = client.get("/denied")

    assert (not_found_response.status_code, not_found_response.json()) == (404, {"detail": "missing"})
    assert (invalid_response.status_code, invalid_response.json()) == (
        400,
        {"detail": "invalid", "field_errors": [{"field": "status", "message": "already closed", "code": "invalid_state"}]},
    )
    assert (conflict_response.status_code, conflict_response.json()) == (409, {"detail": "conflict"})
    assert (denied_response.status_code, denied_response.json()) == (403, {"detail": "denied"})
