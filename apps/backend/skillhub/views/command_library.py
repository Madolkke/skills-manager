from __future__ import annotations

from fastapi import Depends, FastAPI

from skillhub.services import CommandLibraryService
from skillhub.services.command_parsing import CommandParsingService
from skillhub.views.auth import ActorContext, actor_dependency, admin_key_dependency
from skillhub.views.dependencies import command_library_service_dependency, command_parsing_service_dependency
from skillhub.views.request_models.command_parsing import CommandParseErrorResponse, CommandParsePayload, CommandParseResponse
from skillhub.views.responses import result_payload
from skillhub.views.schemas import CommandInstancePayload, CommandSearchPayload, SystemCommandPayload, SystemCommandUpdatePayload


def register_command_library_routes(app: FastAPI) -> None:
    admin_auth = Depends(admin_key_dependency)

    @app.post("/api/command-library/parse", response_model=CommandParseResponse,
              responses={status: {"model": CommandParseErrorResponse} for status in (400, 404, 409, 413, 422, 504)})
    def parse_command_echo(
        payload: CommandParsePayload,
        actor: ActorContext = Depends(actor_dependency),
        service: CommandParsingService = Depends(command_parsing_service_dependency),
    ):
        """匹配已启用系统命令，并使用其受限 TTP 模板解析回显。"""
        return result_payload(service.parse(command=payload.input, echo=payload.echo, actor=actor.id))

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

    @app.post("/api/command-library/system-commands/{command_id}/instantiate-preview")
    def instantiate_command_preview(
        command_id: str,
        payload: CommandInstancePayload,
        actor: ActorContext = Depends(actor_dependency),
        service: CommandLibraryService = Depends(command_library_service_dependency),
    ):
        return result_payload(service.instantiate_preview(command_id=command_id, command=payload.command_template))

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
            service.update_system(command_id=command_id, payload=payload.model_dump(by_alias=True, exclude_unset=True), actor="admin-console")
        )

    @app.delete("/api/admin/system-commands/{command_id}")
    def delete_system_command(
        command_id: str,
        _: None = admin_auth,
        service: CommandLibraryService = Depends(command_library_service_dependency),
    ):
        return result_payload(service.delete_system(command_id=command_id))
