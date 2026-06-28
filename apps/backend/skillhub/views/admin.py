from __future__ import annotations

from fastapi import Depends, FastAPI

from skillhub.views.auth import admin_key_dependency
from skillhub.views.dependencies import admin_service_dependency
from skillhub.views.responses import result_payload
from skillhub.views.schemas import AdminGroupMemberPayload, AdminGroupPayload, AdminOpencodeAgentCreatePayload, AdminOpencodeAgentPayload, AdminPublishTargetUpdatePayload, AdminRoleAssignmentPayload, AdminSkillUpdatePayload, AdminTagGroupPayload, AdminTagGroupUpdatePayload, AdminTagValuePayload
from skillhub.services import AdminService


def register_admin_routes(app: FastAPI) -> None:
    admin_auth = Depends(admin_key_dependency)

    @app.get("/api/admin/skills")
    def admin_skills(_: None = admin_auth, service: AdminService = Depends(admin_service_dependency)):
        return result_payload(service.list_skills())

    @app.patch("/api/admin/skills/{skill_id}")
    def admin_update_skill(
        skill_id: str,
        payload: AdminSkillUpdatePayload,
        _: None = admin_auth,
        service: AdminService = Depends(admin_service_dependency),
    ):
        return result_payload(service.update_skill(skill_id=skill_id, slug=payload.slug, owner_ref=payload.owner_ref, tags=payload.tags))

    @app.get("/api/admin/groups")
    def admin_groups(_: None = admin_auth, service: AdminService = Depends(admin_service_dependency)):
        return result_payload(service.list_groups())

    @app.get("/api/admin/tag-groups")
    def admin_tag_groups(_: None = admin_auth, service: AdminService = Depends(admin_service_dependency)):
        return result_payload(service.list_tag_groups())

    @app.post("/api/admin/tag-groups")
    def admin_create_tag_group(
        payload: AdminTagGroupPayload,
        _: None = admin_auth,
        service: AdminService = Depends(admin_service_dependency),
    ):
        return result_payload(
            service.create_tag_group(
                group_id=payload.id,
                display_name=payload.display_name,
                description=payload.description,
                sort_order=payload.sort_order,
            )
        )

    @app.patch("/api/admin/tag-groups/{tag_group_id}")
    def admin_update_tag_group(
        tag_group_id: str,
        payload: AdminTagGroupUpdatePayload,
        _: None = admin_auth,
        service: AdminService = Depends(admin_service_dependency),
    ):
        return result_payload(
            service.update_tag_group(
                group_id=tag_group_id,
                display_name=payload.display_name,
                description=payload.description,
                sort_order=payload.sort_order,
            )
        )

    @app.delete("/api/admin/tag-groups/{tag_group_id}")
    def admin_delete_tag_group(
        tag_group_id: str,
        _: None = admin_auth,
        service: AdminService = Depends(admin_service_dependency),
    ):
        return result_payload(service.delete_tag_group(group_id=tag_group_id))

    @app.post("/api/admin/tag-groups/{tag_group_id}/values")
    def admin_create_tag_value(
        tag_group_id: str,
        payload: AdminTagValuePayload,
        _: None = admin_auth,
        service: AdminService = Depends(admin_service_dependency),
    ):
        return result_payload(
            service.create_tag_value(
                group_id=tag_group_id,
                value=payload.value,
                display_name=payload.display_name,
                description=payload.description,
                sort_order=payload.sort_order,
            )
        )

    @app.patch("/api/admin/tag-groups/{tag_group_id}/values/{tag_value}")
    def admin_update_tag_value(
        tag_group_id: str,
        tag_value: str,
        payload: AdminTagValuePayload,
        _: None = admin_auth,
        service: AdminService = Depends(admin_service_dependency),
    ):
        return result_payload(
            service.update_tag_value(
                group_id=tag_group_id,
                value=tag_value,
                display_name=payload.display_name,
                description=payload.description,
                sort_order=payload.sort_order,
            )
        )

    @app.delete("/api/admin/tag-groups/{tag_group_id}/values/{tag_value}")
    def admin_delete_tag_value(
        tag_group_id: str,
        tag_value: str,
        _: None = admin_auth,
        service: AdminService = Depends(admin_service_dependency),
    ):
        return result_payload(service.delete_tag_value(group_id=tag_group_id, value=tag_value))

    @app.post("/api/admin/groups")
    def admin_create_group(
        payload: AdminGroupPayload,
        _: None = admin_auth,
        service: AdminService = Depends(admin_service_dependency),
    ):
        return result_payload(service.create_group(name=payload.name, description=payload.description))

    @app.patch("/api/admin/groups/{group_id}")
    def admin_update_group(
        group_id: str,
        payload: AdminGroupPayload,
        _: None = admin_auth,
        service: AdminService = Depends(admin_service_dependency),
    ):
        return result_payload(service.update_group(group_id=group_id, name=payload.name, description=payload.description))

    @app.delete("/api/admin/groups/{group_id}")
    def admin_delete_group(
        group_id: str,
        _: None = admin_auth,
        service: AdminService = Depends(admin_service_dependency),
    ):
        return result_payload(service.delete_group(group_id=group_id))

    @app.post("/api/admin/groups/{group_id}/members")
    def admin_add_group_member(
        group_id: str,
        payload: AdminGroupMemberPayload,
        _: None = admin_auth,
        service: AdminService = Depends(admin_service_dependency),
    ):
        return result_payload(service.add_group_member(group_id=group_id, subject_id=payload.subject_id, subject_type=payload.subject_type))

    @app.delete("/api/admin/groups/{group_id}/members/{subject_id}")
    def admin_remove_group_member(
        group_id: str,
        subject_id: str,
        subject_type: str = "user",
        _: None = admin_auth,
        service: AdminService = Depends(admin_service_dependency),
    ):
        return result_payload(service.remove_group_member(group_id=group_id, subject_id=subject_id, subject_type=subject_type))

    @app.get("/api/admin/role-assignments")
    def admin_role_assignments(_: None = admin_auth, service: AdminService = Depends(admin_service_dependency)):
        return result_payload(service.list_all_role_assignments())

    @app.post("/api/admin/role-assignments")
    def admin_assign_role(
        payload: AdminRoleAssignmentPayload,
        _: None = admin_auth,
        service: AdminService = Depends(admin_service_dependency),
    ):
        return result_payload(
            service.assign_role(
                resource_type=payload.resource_type,
                resource_id=payload.resource_id,
                subject_id=payload.subject_id,
                subject_type=payload.subject_type,
                role=payload.role,
            )
        )

    @app.delete("/api/admin/role-assignments/{role_assignment_id}")
    def admin_revoke_role_assignment(
        role_assignment_id: str,
        _: None = admin_auth,
        service: AdminService = Depends(admin_service_dependency),
    ):
        return result_payload(service.revoke_role_assignment(role_assignment_id=role_assignment_id))

    @app.get("/api/admin/publish-targets")
    def admin_publish_targets(_: None = admin_auth, service: AdminService = Depends(admin_service_dependency)):
        return result_payload(service.list_publish_targets())

    @app.get("/api/admin/publish-gate-checks")
    def admin_publish_gate_checks(_: None = admin_auth, service: AdminService = Depends(admin_service_dependency)):
        return result_payload(service.list_publish_gate_checks())

    @app.patch("/api/admin/publish-targets/{publish_target_id}")
    def admin_update_publish_target(
        publish_target_id: str,
        payload: AdminPublishTargetUpdatePayload,
        _: None = admin_auth,
        service: AdminService = Depends(admin_service_dependency),
    ):
        return result_payload(
            service.update_publish_target(
                publish_target_id=publish_target_id,
                enabled=payload.enabled,
                gate_expression=payload.gate_expression,
            )
        )

    @app.get("/api/admin/publish-records")
    def admin_publish_records(_: None = admin_auth, service: AdminService = Depends(admin_service_dependency)):
        return result_payload(service.list_publish_records())

    @app.get("/api/admin/opencode-agents")
    def admin_opencode_agents(_: None = admin_auth, service: AdminService = Depends(admin_service_dependency)):
        return result_payload(service.list_opencode_agents())

    @app.post("/api/admin/opencode-agents")
    def admin_create_opencode_agent(
        payload: AdminOpencodeAgentCreatePayload,
        _: None = admin_auth,
        service: AdminService = Depends(admin_service_dependency),
    ):
        return result_payload(service.create_opencode_agent(payload=payload.model_dump()))

    @app.patch("/api/admin/opencode-agents/{agent_id}")
    def admin_update_opencode_agent(
        agent_id: str,
        payload: AdminOpencodeAgentPayload,
        _: None = admin_auth,
        service: AdminService = Depends(admin_service_dependency),
    ):
        data = payload.model_dump()
        data["id"] = agent_id
        return result_payload(service.update_opencode_agent(agent_id=agent_id, payload=data))

    @app.delete("/api/admin/opencode-agents/{agent_id}")
    def admin_delete_opencode_agent(
        agent_id: str,
        _: None = admin_auth,
        service: AdminService = Depends(admin_service_dependency),
    ):
        return result_payload(service.delete_opencode_agent(agent_id=agent_id))

    @app.post("/api/admin/publish-records/{publish_record_id}/confirm")
    def admin_confirm_publish_record(
        publish_record_id: str,
        _: None = admin_auth,
        service: AdminService = Depends(admin_service_dependency),
    ):
        return result_payload(service.confirm_publish_record(publish_record_id=publish_record_id))

    @app.post("/api/admin/publish-records/{publish_record_id}/cancel")
    def admin_cancel_publish_record(
        publish_record_id: str,
        _: None = admin_auth,
        service: AdminService = Depends(admin_service_dependency),
    ):
        return result_payload(service.cancel_publish_record(publish_record_id=publish_record_id))
