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


def test_expression_routes_expose_validation_without_evaluation():
    app = FastAPI()
    register_workflow_routes(app)

    paths = app.openapi()["paths"]

    assert "get" in paths["/api/workflow-expression-contract"]
    assert "post" in paths["/api/workflow-expression-validations"]
    assert "post" in paths["/api/workflow-expression-validations/batch"]
    assert "/api/workflow-expression-evaluations" not in paths


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
