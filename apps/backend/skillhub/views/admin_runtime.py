from __future__ import annotations

from fastapi import Depends, FastAPI

from skillhub.services import AdminService
from skillhub.views.dependencies import admin_service_dependency
from skillhub.views.responses import result_payload
from skillhub.views.schemas import AdminOpencodeAgentCreatePayload, AdminOpencodeAgentPayload, AdminPublishTargetUpdatePayload


def register_admin_runtime_routes(app: FastAPI, admin_auth) -> None:
    @app.get("/api/admin/publish-targets")
    def publish_targets(_: None = admin_auth, service: AdminService = Depends(admin_service_dependency)):
        return result_payload(service.list_publish_targets())

    @app.get("/api/admin/publish-gate-checks")
    def publish_gate_checks(_: None = admin_auth, service: AdminService = Depends(admin_service_dependency)):
        return result_payload(service.list_publish_gate_checks())

    @app.patch("/api/admin/publish-targets/{publish_target_id}")
    def update_publish_target(
        publish_target_id: str,
        payload: AdminPublishTargetUpdatePayload,
        _: None = admin_auth,
        service: AdminService = Depends(admin_service_dependency),
    ):
        return result_payload(
            service.update_publish_target(
                publish_target_id=publish_target_id,
                enabled=payload.enabled,
                auto_publish_enabled=payload.auto_publish_enabled,
                gate_expression=payload.gate_expression,
            )
        )

    @app.get("/api/admin/publish-records")
    def publish_records(_: None = admin_auth, service: AdminService = Depends(admin_service_dependency)):
        return result_payload(service.list_publish_records())

    @app.get("/api/admin/workers")
    def workers(_: None = admin_auth, service: AdminService = Depends(admin_service_dependency)):
        return result_payload(service.list_workers())

    @app.get("/api/admin/opencode-agents")
    def opencode_agents(_: None = admin_auth, service: AdminService = Depends(admin_service_dependency)):
        return result_payload(service.list_opencode_agents())

    @app.post("/api/admin/opencode-agents")
    def create_opencode_agent(
        payload: AdminOpencodeAgentCreatePayload,
        _: None = admin_auth,
        service: AdminService = Depends(admin_service_dependency),
    ):
        return result_payload(service.create_opencode_agent(payload=payload.model_dump()))

    @app.patch("/api/admin/opencode-agents/{agent_id}")
    def update_opencode_agent(
        agent_id: str,
        payload: AdminOpencodeAgentPayload,
        _: None = admin_auth,
        service: AdminService = Depends(admin_service_dependency),
    ):
        data = payload.model_dump()
        data["id"] = agent_id
        return result_payload(service.update_opencode_agent(agent_id=agent_id, payload=data))

    @app.delete("/api/admin/opencode-agents/{agent_id}")
    def delete_opencode_agent(
        agent_id: str,
        _: None = admin_auth,
        service: AdminService = Depends(admin_service_dependency),
    ):
        return result_payload(service.delete_opencode_agent(agent_id=agent_id))

    @app.post("/api/admin/publish-records/{publish_record_id}/confirm")
    def confirm_publish_record(
        publish_record_id: str,
        _: None = admin_auth,
        service: AdminService = Depends(admin_service_dependency),
    ):
        return result_payload(service.confirm_publish_record(publish_record_id=publish_record_id))

    @app.post("/api/admin/publish-records/{publish_record_id}/cancel")
    def cancel_publish_record(
        publish_record_id: str,
        _: None = admin_auth,
        service: AdminService = Depends(admin_service_dependency),
    ):
        return result_payload(service.cancel_publish_record(publish_record_id=publish_record_id))
