from __future__ import annotations

from fastapi import Depends, FastAPI

from skillhub.services import CommandLibraryService
from skillhub.views.auth import ActorContext, actor_dependency, admin_key_dependency
from skillhub.views.dependencies import command_library_service_dependency
from skillhub.views.responses import result_payload
from skillhub.views.schemas import CommandSearchPayload, SystemCommandPayload, SystemCommandUpdatePayload


def register_command_library_routes(app: FastAPI) -> None:
    admin_auth = Depends(admin_key_dependency)

    @app.post("/api/command-library/search")
    def search_command_library(
        payload: CommandSearchPayload,
        actor: ActorContext = Depends(actor_dependency),
        service: CommandLibraryService = Depends(command_library_service_dependency),
    ):
        return result_payload(
            service.search(
                command=payload.command,
                actor=actor.id,
                include_user=payload.include_user,
                target_version=payload.target_version,
                owner_ref=payload.owner_ref,
                include_system=payload.include_system,
                include_disabled=payload.include_disabled,
                partial=payload.partial,
                prefix=payload.prefix,
            )
        )

    @app.get("/api/admin/system-commands")
    def list_system_commands(
        _: None = admin_auth,
        service: CommandLibraryService = Depends(command_library_service_dependency),
    ):
        return result_payload(service.list_system())

    @app.post("/api/admin/system-commands")
    def create_system_command(
        payload: SystemCommandPayload,
        _: None = admin_auth,
        service: CommandLibraryService = Depends(command_library_service_dependency),
    ):
        return result_payload(service.create_system(payload=payload.model_dump(by_alias=True), actor="admin-console"))

    @app.get("/api/admin/system-commands/{command_id}")
    def get_system_command(
        command_id: str,
        _: None = admin_auth,
        service: CommandLibraryService = Depends(command_library_service_dependency),
    ):
        return result_payload(service.get_system(command_id=command_id))

    @app.put("/api/admin/system-commands/{command_id}")
    @app.patch("/api/admin/system-commands/{command_id}")
    def update_system_command(
        command_id: str,
        payload: SystemCommandUpdatePayload,
        _: None = admin_auth,
        service: CommandLibraryService = Depends(command_library_service_dependency),
    ):
        return result_payload(
            service.update_system(command_id=command_id, payload=payload.model_dump(by_alias=True), actor="admin-console")
        )

    @app.delete("/api/admin/system-commands/{command_id}")
    def delete_system_command(
        command_id: str,
        _: None = admin_auth,
        service: CommandLibraryService = Depends(command_library_service_dependency),
    ):
        return result_payload(service.delete_system(command_id=command_id))
