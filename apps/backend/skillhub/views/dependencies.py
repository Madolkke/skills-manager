from __future__ import annotations

from collections.abc import Iterator
from os import environ

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from skillhub.models.store import SkillHubStore
from skillhub.services import (
    AdminService,
    ArtifactService,
    EvaluationReadService,
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


def session_dependency(request: Request) -> Iterator[Session]:
    with request.app.state.session_factory.begin() as session:
        yield session


def store_dependency(session: Session = Depends(session_dependency)) -> SkillHubStore:
    return SkillHubStore(session)


def skill_service_dependency(session: Session = Depends(session_dependency)) -> SkillService:
    return SkillService(SkillHubStore(session))


def version_service_dependency(session: Session = Depends(session_dependency)) -> VersionService:
    return VersionService(SkillHubStore(session))


def workflow_service_dependency(session: Session = Depends(session_dependency)) -> WorkflowService:
    return WorkflowService(SkillHubStore(session))


def review_service_dependency(session: Session = Depends(session_dependency)) -> ReviewService:
    return ReviewService(SkillHubStore(session))


def evaluation_service_dependency(session: Session = Depends(session_dependency)) -> EvaluationService:
    return EvaluationService(SkillHubStore(session))


def admin_service_dependency(session: Session = Depends(session_dependency)) -> AdminService:
    return AdminService(SkillHubStore(session))


def external_skill_service_dependency(session: Session = Depends(session_dependency)) -> ExternalSkillService:
    return ExternalSkillService(SkillHubStore(session))


def opencode_service_dependency(session: Session = Depends(session_dependency)) -> OpencodeService:
    return OpencodeService(SkillHubStore(session), environ)


def saved_view_service_dependency(session: Session = Depends(session_dependency)) -> SavedViewService:
    return SavedViewService(SkillHubStore(session))


def skill_builder_service_dependency(session: Session = Depends(session_dependency)) -> SkillBuilderService:
    return SkillBuilderService(SkillHubStore(session))


def artifact_service_dependency(session: Session = Depends(session_dependency)) -> ArtifactService:
    return ArtifactService(SkillHubStore(session))


def evaluation_read_service_dependency(session: Session = Depends(session_dependency)) -> EvaluationReadService:
    return EvaluationReadService(SkillHubStore(session))
