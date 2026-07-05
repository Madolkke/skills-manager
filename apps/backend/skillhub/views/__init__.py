from __future__ import annotations

from fastapi import FastAPI

from skillhub.views.admin import register_admin_routes
from skillhub.views.artifacts import register_artifact_routes
from skillhub.views.evaluations import register_evaluation_routes
from skillhub.views.external import register_external_routes
from skillhub.views.opencode import register_opencode_routes
from skillhub.views.reviews import register_review_routes
from skillhub.views.saved_views import register_saved_view_routes
from skillhub.views.session import register_session_routes
from skillhub.views.skill_builder import register_skill_builder_routes
from skillhub.views.skills import register_skill_routes
from skillhub.views.system import register_system_routes
from skillhub.views.versions import register_version_routes


def register_views(app: FastAPI) -> None:
    register_system_routes(app)
    register_session_routes(app)
    register_admin_routes(app)
    register_external_routes(app)
    register_opencode_routes(app)
    register_skill_builder_routes(app)
    register_skill_routes(app)
    register_version_routes(app)
    register_evaluation_routes(app)
    register_review_routes(app)
    register_saved_view_routes(app)
    register_artifact_routes(app)
