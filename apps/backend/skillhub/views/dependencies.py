from __future__ import annotations

from os import environ
from typing import Mapping

from fastapi import Request
from sqlalchemy import Engine, create_engine

from skillhub.models.store import SkillHubStore
from skillhub.services import (
    AdminService,
    ArtifactService,
    EvaluationService,
    ExternalSkillService,
    OpencodeService,
    ReviewService,
    SavedViewService,
    SkillBuilderService,
    SkillService,
    VersionService,
    WorkflowService,
)


POSTGRESQL_SCHEMES = ("postgresql://", "postgresql+psycopg://")


def resolve_database_url(environment: Mapping[str, str] = environ) -> str:
    database_url = environment.get("SKILLHUB_DATABASE_URL")
    if not database_url:
        raise ValueError("SKILLHUB_DATABASE_URL is required and must point to a PostgreSQL database.")
    validate_postgres_url(database_url)
    return database_url


def create_postgres_engine(database_url: str) -> Engine:
    validate_postgres_url(database_url)
    return create_engine(database_url, pool_pre_ping=True)


def validate_postgres_url(database_url: str) -> None:
    if not database_url.startswith(POSTGRESQL_SCHEMES):
        raise ValueError("SKILLHUB_DATABASE_URL must use postgresql:// or postgresql+psycopg://.")


def store_dependency(request: Request) -> SkillHubStore:
    return _store(request)


def skill_service_dependency(request: Request) -> SkillService:
    return SkillService(_store(request))


def version_service_dependency(request: Request) -> VersionService:
    return VersionService(_store(request))


def workflow_service_dependency(request: Request) -> WorkflowService:
    return WorkflowService(_store(request))


def review_service_dependency(request: Request) -> ReviewService:
    return ReviewService(_store(request))


def evaluation_service_dependency(request: Request) -> EvaluationService:
    return EvaluationService(_store(request))


def admin_service_dependency(request: Request) -> AdminService:
    return AdminService(_store(request))


def external_skill_service_dependency(request: Request) -> ExternalSkillService:
    return ExternalSkillService(_store(request))


def opencode_service_dependency(request: Request) -> OpencodeService:
    return OpencodeService(_store(request), environ)


def saved_view_service_dependency(request: Request) -> SavedViewService:
    return SavedViewService(_store(request))


def skill_builder_service_dependency(request: Request) -> SkillBuilderService:
    return SkillBuilderService(_store(request))


def artifact_service_dependency(request: Request) -> ArtifactService:
    return ArtifactService(_store(request))


def _store(request: Request) -> SkillHubStore:
    return SkillHubStore(request.app.state.engine)
