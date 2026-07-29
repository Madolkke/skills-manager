from fastapi import FastAPI

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
