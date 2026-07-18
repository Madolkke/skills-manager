from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from skillhub.models.schema.base import Base, CreatedAtMixin

if TYPE_CHECKING:
    from skillhub.models.schema.evaluations import EvalCaseVersion
    from skillhub.models.schema.skills import Skill
    from skillhub.models.schema.workflows import WorkflowSync


class Artifact(CreatedAtMixin, Base):
    __tablename__ = "artifacts"
    __table_args__ = (
        CheckConstraint("size_bytes >= 0", name="artifacts_size_bytes_non_negative"),
        UniqueConstraint("locator", "digest", name="artifacts_locator_digest_unique"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    namespace: Mapped[str] = mapped_column(Text, nullable=False)
    locator: Mapped[str] = mapped_column(Text, nullable=False)
    digest: Mapped[str] = mapped_column(Text, nullable=False)
    media_type: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
    content_text: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(Text, nullable=False)

    eval_case_versions: Mapped[list["EvalCaseVersion"]] = relationship(back_populates="workspace_artifact", lazy="raise")
    workflow_syncs: Mapped[list["WorkflowSync"]] = relationship(back_populates="source_artifact", lazy="raise")


class SavedView(CreatedAtMixin, Base):
    __tablename__ = "saved_views"
    __table_args__ = (
        CheckConstraint("view_type in ('run_history')", name="saved_views_type_check"),
        UniqueConstraint("skill_id", "view_type", "name", name="saved_views_skill_type_name_unique"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    skill_id: Mapped[str] = mapped_column(Text, ForeignKey("skills.id"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    view_type: Mapped[str] = mapped_column(Text, nullable=False)
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_by: Mapped[str] = mapped_column(Text, nullable=False)

    skill: Mapped["Skill"] = relationship(back_populates="saved_views", lazy="raise")
