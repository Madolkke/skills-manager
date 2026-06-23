from __future__ import annotations

from fastapi import FastAPI

from skillhub.api.routes.admin import register_admin_routes
from skillhub.api.routes.artifacts import register_artifact_routes
from skillhub.api.routes.evaluations import register_evaluation_routes
from skillhub.api.routes.external import register_external_routes
from skillhub.api.routes.saved_views import register_saved_view_routes
from skillhub.api.routes.session import register_session_routes
from skillhub.api.routes.skills import register_skill_routes
from skillhub.api.routes.system import register_system_routes
from skillhub.api.routes.versions import register_version_routes


def register_routes(app: FastAPI) -> None:
    register_system_routes(app)
    register_session_routes(app)
    register_admin_routes(app)
    register_external_routes(app)
    register_skill_routes(app)
    register_version_routes(app)
    register_evaluation_routes(app)
    register_saved_view_routes(app)
    register_artifact_routes(app)
