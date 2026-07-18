from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import CheckConstraint, ForeignKey, Integer, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from skillhub.models.schema.base import Base, CreatedAtMixin, UpdatedAtMixin

if TYPE_CHECKING:
    from skillhub.models.schema.artifacts import Artifact
    from skillhub.models.schema.skills import Skill, SkillVersion


class Workflow(CreatedAtMixin, UpdatedAtMixin, Base):
    __tablename__ = "workflows"
    __table_args__ = (
        CheckConstraint("revision > 0", name="workflows_revision_positive"),
        CheckConstraint("document_schema_version > 0", name="workflows_schema_version_positive"),
        CheckConstraint("jsonb_typeof(document) = 'object'", name="workflows_document_object"),
        UniqueConstraint("skill_id", name="workflows_skill_unique"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    skill_id: Mapped[str] = mapped_column(Text, ForeignKey("skills.id"), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    document_schema_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("3"))
    document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    document_digest: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    last_saved_by: Mapped[str] = mapped_column(Text, nullable=False)

    skill: Mapped["Skill"] = relationship(back_populates="workflow", lazy="raise")
    syncs: Mapped[list["WorkflowSync"]] = relationship(back_populates="workflow", lazy="raise")


class WorkflowCollectionDefinition(CreatedAtMixin, UpdatedAtMixin, Base):
    __tablename__ = "workflow_collection_definitions"
    __table_args__ = (
        CheckConstraint("latest_revision > 0", name="workflow_collection_definitions_revision_positive"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    latest_revision: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    created_by: Mapped[str] = mapped_column(Text, nullable=False)

    revisions: Mapped[list["WorkflowCollectionRevision"]] = relationship(back_populates="definition_record", lazy="raise")


class WorkflowCollectionRevision(CreatedAtMixin, Base):
    __tablename__ = "workflow_collection_revisions"
    __table_args__ = (
        CheckConstraint("revision > 0", name="workflow_collection_revisions_revision_positive"),
        CheckConstraint("document_schema_version > 0", name="workflow_collection_revisions_schema_version_positive"),
        CheckConstraint("jsonb_typeof(definition) = 'object'", name="workflow_collection_revisions_definition_object"),
    )

    definition_id: Mapped[str] = mapped_column(Text, ForeignKey("workflow_collection_definitions.id"), primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_schema_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("3"))
    definition: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    definition_digest: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str] = mapped_column(Text, nullable=False)

    definition_record: Mapped[WorkflowCollectionDefinition] = relationship(back_populates="revisions", lazy="raise")


class WorkflowSync(CreatedAtMixin, Base):
    __tablename__ = "workflow_syncs"
    __table_args__ = (
        CheckConstraint("workflow_revision > 0", name="workflow_syncs_revision_positive"),
        CheckConstraint("document_schema_version > 0", name="workflow_syncs_schema_version_positive"),
        UniqueConstraint("workflow_id", "workflow_revision", name="workflow_syncs_workflow_revision_unique"),
        UniqueConstraint("skill_version_id", name="workflow_syncs_skill_version_unique"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    workflow_id: Mapped[str] = mapped_column(Text, ForeignKey("workflows.id"), nullable=False)
    workflow_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    document_schema_version: Mapped[int] = mapped_column(Integer, nullable=False)
    source_artifact_id: Mapped[str] = mapped_column(Text, ForeignKey("artifacts.id"), nullable=False)
    skill_version_id: Mapped[str] = mapped_column(Text, ForeignKey("skill_versions.id"), nullable=False)
    generator_version: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str] = mapped_column(Text, nullable=False)

    workflow: Mapped[Workflow] = relationship(back_populates="syncs", lazy="raise")
    skill_version: Mapped["SkillVersion"] = relationship(back_populates="workflow_sync", lazy="raise")
    source_artifact: Mapped["Artifact"] = relationship(back_populates="workflow_syncs", lazy="raise")
