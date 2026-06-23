from __future__ import annotations

from fastapi import Depends, FastAPI

from skillhub.api.auth import admin_key_dependency
from skillhub.api.database import repository_dependency
from skillhub.api.responses import result_payload
from skillhub.api.schemas import AdminGroupMemberPayload, AdminGroupPayload, AdminRoleAssignmentPayload, AdminSkillUpdatePayload, AdminTagGroupPayload, AdminTagGroupUpdatePayload, AdminTagValuePayload
from skillhub.infrastructure.db.repositories import SqlSkillRepository


def register_admin_routes(app: FastAPI) -> None:
    admin_auth = Depends(admin_key_dependency)

    @app.get("/api/admin/skills")
    def admin_skills(_: None = admin_auth, repository: SqlSkillRepository = Depends(repository_dependency)):
        return result_payload(repository.list_skills())

    @app.patch("/api/admin/skills/{skill_id}")
    def admin_update_skill(
        skill_id: str,
        payload: AdminSkillUpdatePayload,
        _: None = admin_auth,
        repository: SqlSkillRepository = Depends(repository_dependency),
    ):
        return result_payload(repository.update_skill_admin(skill_id=skill_id, slug=payload.slug, owner_ref=payload.owner_ref, tags=payload.tags))

    @app.get("/api/admin/groups")
    def admin_groups(_: None = admin_auth, repository: SqlSkillRepository = Depends(repository_dependency)):
        return result_payload(repository.list_groups())

    @app.get("/api/admin/tag-groups")
    def admin_tag_groups(_: None = admin_auth, repository: SqlSkillRepository = Depends(repository_dependency)):
        return result_payload(repository.list_tag_groups())

    @app.post("/api/admin/tag-groups")
    def admin_create_tag_group(
        payload: AdminTagGroupPayload,
        _: None = admin_auth,
        repository: SqlSkillRepository = Depends(repository_dependency),
    ):
        return result_payload(
            repository.create_tag_group(
                group_id=payload.id,
                display_name=payload.display_name,
                description=payload.description,
                sort_order=payload.sort_order,
                actor="admin-console",
            )
        )

    @app.patch("/api/admin/tag-groups/{tag_group_id}")
    def admin_update_tag_group(
        tag_group_id: str,
        payload: AdminTagGroupUpdatePayload,
        _: None = admin_auth,
        repository: SqlSkillRepository = Depends(repository_dependency),
    ):
        return result_payload(
            repository.update_tag_group(
                group_id=tag_group_id,
                display_name=payload.display_name,
                description=payload.description,
                sort_order=payload.sort_order,
                actor="admin-console",
            )
        )

    @app.delete("/api/admin/tag-groups/{tag_group_id}")
    def admin_delete_tag_group(
        tag_group_id: str,
        _: None = admin_auth,
        repository: SqlSkillRepository = Depends(repository_dependency),
    ):
        return result_payload(repository.delete_tag_group_admin(group_id=tag_group_id))

    @app.post("/api/admin/tag-groups/{tag_group_id}/values")
    def admin_create_tag_value(
        tag_group_id: str,
        payload: AdminTagValuePayload,
        _: None = admin_auth,
        repository: SqlSkillRepository = Depends(repository_dependency),
    ):
        return result_payload(
            repository.create_tag_value(
                group_id=tag_group_id,
                value=payload.value,
                display_name=payload.display_name,
                description=payload.description,
                sort_order=payload.sort_order,
                actor="admin-console",
            )
        )

    @app.patch("/api/admin/tag-groups/{tag_group_id}/values/{tag_value}")
    def admin_update_tag_value(
        tag_group_id: str,
        tag_value: str,
        payload: AdminTagValuePayload,
        _: None = admin_auth,
        repository: SqlSkillRepository = Depends(repository_dependency),
    ):
        return result_payload(
            repository.update_tag_value(
                group_id=tag_group_id,
                value=tag_value,
                display_name=payload.display_name,
                description=payload.description,
                sort_order=payload.sort_order,
                actor="admin-console",
            )
        )

    @app.delete("/api/admin/tag-groups/{tag_group_id}/values/{tag_value}")
    def admin_delete_tag_value(
        tag_group_id: str,
        tag_value: str,
        _: None = admin_auth,
        repository: SqlSkillRepository = Depends(repository_dependency),
    ):
        return result_payload(repository.delete_tag_value_admin(group_id=tag_group_id, value=tag_value))

    @app.post("/api/admin/groups")
    def admin_create_group(
        payload: AdminGroupPayload,
        _: None = admin_auth,
        repository: SqlSkillRepository = Depends(repository_dependency),
    ):
        return result_payload(repository.create_group(name=payload.name, description=payload.description, actor="admin-console"))

    @app.patch("/api/admin/groups/{group_id}")
    def admin_update_group(
        group_id: str,
        payload: AdminGroupPayload,
        _: None = admin_auth,
        repository: SqlSkillRepository = Depends(repository_dependency),
    ):
        return result_payload(repository.update_group(group_id=group_id, name=payload.name, description=payload.description, actor="admin-console"))

    @app.delete("/api/admin/groups/{group_id}")
    def admin_delete_group(
        group_id: str,
        _: None = admin_auth,
        repository: SqlSkillRepository = Depends(repository_dependency),
    ):
        return result_payload(repository.delete_group_admin(group_id=group_id))

    @app.post("/api/admin/groups/{group_id}/members")
    def admin_add_group_member(
        group_id: str,
        payload: AdminGroupMemberPayload,
        _: None = admin_auth,
        repository: SqlSkillRepository = Depends(repository_dependency),
    ):
        return result_payload(repository.add_group_member(group_id=group_id, subject_id=payload.subject_id, subject_type=payload.subject_type, actor="admin-console"))

    @app.delete("/api/admin/groups/{group_id}/members/{subject_id}")
    def admin_remove_group_member(
        group_id: str,
        subject_id: str,
        subject_type: str = "user",
        _: None = admin_auth,
        repository: SqlSkillRepository = Depends(repository_dependency),
    ):
        return result_payload(repository.remove_group_member(group_id=group_id, subject_id=subject_id, subject_type=subject_type))

    @app.get("/api/admin/role-assignments")
    def admin_role_assignments(_: None = admin_auth, repository: SqlSkillRepository = Depends(repository_dependency)):
        return result_payload(repository.list_all_role_assignments())

    @app.post("/api/admin/role-assignments")
    def admin_assign_role(
        payload: AdminRoleAssignmentPayload,
        _: None = admin_auth,
        repository: SqlSkillRepository = Depends(repository_dependency),
    ):
        return result_payload(
            repository.assign_role(
                resource_type=payload.resource_type,
                resource_id=payload.resource_id,
                subject_id=payload.subject_id,
                subject_type=payload.subject_type,
                role=payload.role,
                actor="admin-console",
                require_permission=False,
            )
        )

    @app.delete("/api/admin/role-assignments/{role_assignment_id}")
    def admin_revoke_role_assignment(
        role_assignment_id: str,
        _: None = admin_auth,
        repository: SqlSkillRepository = Depends(repository_dependency),
    ):
        return result_payload(repository.revoke_role_assignment_admin(role_assignment_id=role_assignment_id))
