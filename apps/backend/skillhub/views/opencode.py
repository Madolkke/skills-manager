from __future__ import annotations

from fastapi import Depends, FastAPI

from skillhub.services import OpencodeService
from skillhub.views.dependencies import opencode_service_dependency


def register_opencode_routes(app: FastAPI) -> None:
    @app.get("/api/opencode/providers")
    def opencode_providers(service: OpencodeService = Depends(opencode_service_dependency)):
        return service.provider_options()
