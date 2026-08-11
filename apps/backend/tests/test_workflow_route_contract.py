from fastapi import FastAPI
from fastapi.testclient import TestClient

from skillhub.models.rules.executor_workflows import ExecutorWorkflow
from skillhub.views.dependencies import executor_workflow_service_dependency, workflow_service_dependency
from skillhub.views.executor_workflows import register_executor_workflow_routes
from skillhub.views.workflows import register_workflow_routes


def test_workflow_import_accepts_json_request_body():
    app = FastAPI()
    register_workflow_routes(app)

    operation = app.openapi()["paths"]["/api/skills/{skill_id}/workflow/import"]["post"]

    assert "requestBody" in operation
    assert all(item["name"] != "payload" for item in operation.get("parameters", []))


def test_workflow_export_has_strict_portable_bundle_response() -> None:
    app = FastAPI()
    register_workflow_routes(app)

    operation = app.openapi()["paths"]["/api/skills/{skill_id}/workflow/export"]["get"]

    assert operation["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/WorkflowImportBundle"
    }


def test_expression_routes_expose_validation_without_evaluation():
    app = FastAPI()
    register_workflow_routes(app)

    paths = app.openapi()["paths"]

    assert "get" in paths["/api/workflow-expression-contract"]
    assert "post" in paths["/api/workflow-expression-validations"]
    assert "post" in paths["/api/workflow-expression-validations/batch"]
    assert "/api/workflow-expression-evaluations" not in paths


def test_batch_expression_route_validates_payload_shape_and_preserves_request_order():
    class StubService:
        def validate_expressions(self, *, expressions, environment):
            return {"validations": [{"id": item["id"], "inferredType": {"kind": "boolean"}, "diagnostics": []} for item in expressions]}

    app = FastAPI()
    register_workflow_routes(app)
    app.dependency_overrides[workflow_service_dependency] = StubService
    client = TestClient(app)
    response = client.post("/api/workflow-expression-validations/batch", json={
        "expressions": [{"id": "second", "source": "False"}, {"id": "first", "source": "True"}],
        "environment": {"inputs": {}, "outputs": {}, "config": {}},
    })

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["validations"]] == ["second", "first"]
    duplicate = client.post("/api/workflow-expression-validations/batch", json={
        "expressions": [{"id": "same", "source": "True"}, {"id": "same", "source": "False"}],
        "environment": {"inputs": {}, "outputs": {}, "config": {}},
    })
    assert duplicate.status_code == 422

    too_many = client.post("/api/workflow-expression-validations/batch", json={
        "expressions": [{"id": str(index), "source": "True"} for index in range(1001)],
        "environment": {"inputs": {}, "outputs": {}, "config": {}},
    })
    assert too_many.status_code == 422


def test_workflow_log_schema_route_is_authenticated_and_returns_fixed_catalog():
    class StubService:
        def log_schema(self):
            return {
                "document_schema_version": 5,
                "dialect": "duckdb",
                "logs_table": "logs",
                "params_table": "params",
                "columns": [],
            }

    app = FastAPI()
    register_workflow_routes(app)
    app.dependency_overrides[workflow_service_dependency] = StubService

    response = TestClient(app).get("/api/workflow-log-schema")

    assert response.status_code == 200
    assert response.json() == {
        "document_schema_version": 5,
        "dialect": "duckdb",
        "logs_table": "logs",
        "params_table": "params",
        "columns": [],
    }
    operation = app.openapi()["paths"]["/api/workflow-log-schema"]["get"]
    assert operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith("WorkflowLogSchemaResponse")


def test_executor_workflow_route_is_unauthenticated_and_strictly_typed():
    app = FastAPI()
    register_executor_workflow_routes(app)

    operation = app.openapi()["paths"]["/api/skills/{skill_id}/workflow/executor"]["get"]

    assert [item["name"] for item in operation["parameters"]] == ["skill_id"]
    assert operation["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/ExecutorWorkflow"
    }


def test_executor_workflow_route_returns_flat_body_without_actor():
    class StubService:
        def current(self, *, skill_id: str) -> ExecutorWorkflow:
            assert skill_id == "skill-1"
            return ExecutorWorkflow(id=1, name="检查", start_step_ids=[], inputs=[], steps=[], conclusions=[])

    app = FastAPI()
    register_executor_workflow_routes(app)
    app.dependency_overrides[executor_workflow_service_dependency] = StubService

    response = TestClient(app).get("/api/skills/skill-1/workflow/executor")

    assert response.status_code == 200
    assert response.json() == {"id": 1, "name": "检查", "start_step_ids": [], "inputs": [], "steps": [], "conclusions": []}
