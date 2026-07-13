from fastapi import FastAPI

from skillhub.views.workflows import register_workflow_routes


def test_workflow_import_accepts_json_request_body():
    app = FastAPI()
    register_workflow_routes(app)

    operation = app.openapi()["paths"]["/api/skills/{skill_id}/workflow/import"]["post"]

    assert "requestBody" in operation
    assert all(item["name"] != "payload" for item in operation.get("parameters", []))
