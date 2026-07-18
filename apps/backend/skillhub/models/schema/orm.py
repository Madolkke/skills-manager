from __future__ import annotations

from typing import Any, TypeVar

from sqlalchemy import inspect, select
from sqlalchemy.orm import DeclarativeBase, InstrumentedAttribute
from sqlalchemy.sql import Select

from skillhub.models.schema.access import AuditEvent, Group, GroupMembership, Notification, RoleAssignment, TagGroup, TagGroupCascade, TagValue
from skillhub.models.schema.artifacts import Artifact, SavedView
from skillhub.models.schema.evaluations import AcceptedVerification, CaseResult, EvalCase, EvalCaseRun, EvalCaseVersion, EvalRun, EvalSet, EvalSetCase
from skillhub.models.schema.reviews import (
    PublishRecord,
    PublishTarget,
    ReviewCheckResult,
    ReviewRequest,
    ReviewRequestPublishTarget,
    ReviewRequestReviewer,
    ReviewResponse,
)
from skillhub.models.schema.runtime import Job, OpencodeAgent, SkillBuilderMessage, SkillBuilderSession, WorkerHeartbeat
from skillhub.models.schema.skills import Skill, SkillTag, SkillVersion
from skillhub.models.schema.workflows import Workflow, WorkflowCollectionDefinition, WorkflowCollectionRevision, WorkflowSync

ModelT = TypeVar("ModelT", bound=DeclarativeBase)


def entity_columns(model: type[ModelT]) -> tuple[InstrumentedAttribute[Any], ...]:
    """Return mapped columns labelled with their stable database column names."""
    mapper = inspect(model)
    return tuple(
        getattr(model, attribute.key).label(attribute.columns[0].name)
        for attribute in mapper.column_attrs
    )


def select_entity(model: type[ModelT]) -> Select[Any]:
    return select(*entity_columns(model))


__all__ = [
    "AcceptedVerification",
    "Artifact",
    "AuditEvent",
    "CaseResult",
    "EvalCase",
    "EvalCaseRun",
    "EvalCaseVersion",
    "EvalRun",
    "EvalSet",
    "EvalSetCase",
    "Group",
    "GroupMembership",
    "Job",
    "Notification",
    "OpencodeAgent",
    "PublishRecord",
    "PublishTarget",
    "ReviewCheckResult",
    "ReviewRequest",
    "ReviewRequestPublishTarget",
    "ReviewRequestReviewer",
    "ReviewResponse",
    "RoleAssignment",
    "SavedView",
    "Skill",
    "SkillBuilderMessage",
    "SkillBuilderSession",
    "SkillTag",
    "SkillVersion",
    "TagGroup",
    "TagGroupCascade",
    "TagValue",
    "WorkerHeartbeat",
    "Workflow",
    "WorkflowCollectionDefinition",
    "WorkflowCollectionRevision",
    "WorkflowSync",
    "entity_columns",
    "select_entity",
]
