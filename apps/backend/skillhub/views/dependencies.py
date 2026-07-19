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


def store_dependency(session: Session = Depends(session_dependency, scope="function")) -> SkillHubStore:
    return SkillHubStore(session)


def skill_service_dependency(session: Session = Depends(session_dependency, scope="function")) -> SkillService:
    return SkillService(SkillHubStore(session))


def version_service_dependency(session: Session = Depends(session_dependency, scope="function")) -> VersionService:
    return VersionService(SkillHubStore(session))


def workflow_service_dependency(session: Session = Depends(session_dependency, scope="function")) -> WorkflowService:
    return WorkflowService(SkillHubStore(session))


def review_service_dependency(session: Session = Depends(session_dependency, scope="function")) -> ReviewService:
    return ReviewService(SkillHubStore(session))


def evaluation_service_dependency(session: Session = Depends(session_dependency, scope="function")) -> EvaluationService:
    return EvaluationService(SkillHubStore(session))


def admin_service_dependency(session: Session = Depends(session_dependency, scope="function")) -> AdminService:
    return AdminService(SkillHubStore(session))


def external_skill_service_dependency(session: Session = Depends(session_dependency, scope="function")) -> ExternalSkillService:
    return ExternalSkillService(SkillHubStore(session))


def opencode_service_dependency(session: Session = Depends(session_dependency, scope="function")) -> OpencodeService:
    return OpencodeService(SkillHubStore(session), environ)


def saved_view_service_dependency(session: Session = Depends(session_dependency, scope="function")) -> SavedViewService:
    return SavedViewService(SkillHubStore(session))


def skill_builder_service_dependency(session: Session = Depends(session_dependency, scope="function")) -> SkillBuilderService:
    return SkillBuilderService(SkillHubStore(session))


def artifact_service_dependency(session: Session = Depends(session_dependency, scope="function")) -> ArtifactService:
    return ArtifactService(SkillHubStore(session))


def evaluation_read_service_dependency(session: Session = Depends(session_dependency, scope="function")) -> EvaluationReadService:
    return EvaluationReadService(SkillHubStore(session))
