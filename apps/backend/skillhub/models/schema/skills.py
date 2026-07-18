from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import CheckConstraint, ForeignKey, ForeignKeyConstraint, Integer, Text, UniqueConstraint, and_, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, foreign, mapped_column, relationship

from skillhub.models.schema.base import Base, CreatedAtMixin, UpdatedAtMixin

if TYPE_CHECKING:
    from skillhub.models.schema.artifacts import SavedView
    from skillhub.models.schema.evaluations import EvalCase, EvalRun, EvalSet
    from skillhub.models.schema.reviews import ReviewRequest
    from skillhub.models.schema.workflows import Workflow, WorkflowSync


class Skill(CreatedAtMixin, UpdatedAtMixin, Base):
    __tablename__ = "skills"
    __table_args__ = (
        UniqueConstraint("slug", name="skills_slug_unique"),
        CheckConstraint("lifecycle_status in ('active', 'archived')", name="skills_lifecycle_status_check"),
        ForeignKeyConstraint(
            ["current_version_id", "id"],
            ["skill_versions.id", "skill_versions.skill_id"],
            name="skills_current_version_fkey",
            use_alter=True,
        ),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    slug: Mapped[str] = mapped_column(Text, nullable=False)
    owner_ref: Mapped[str] = mapped_column(Text, nullable=False)
    current_version_id: Mapped[str | None] = mapped_column(Text)
    lifecycle_status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'active'"))

    versions: Mapped[list["SkillVersion"]] = relationship(
        back_populates="skill",
        foreign_keys="SkillVersion.skill_id",
        lazy="raise",
    )
    current_version: Mapped["SkillVersion | None"] = relationship(
        primaryjoin=lambda: and_(
            foreign(Skill.current_version_id) == SkillVersion.id,
            Skill.id == SkillVersion.skill_id,
        ),
        back_populates="current_for_skill",
        viewonly=True,
        lazy="raise",
    )
    eval_sets: Mapped[list["EvalSet"]] = relationship(back_populates="skill", lazy="raise")
    eval_cases: Mapped[list["EvalCase"]] = relationship(back_populates="skill", lazy="raise")
    workflow: Mapped["Workflow | None"] = relationship(back_populates="skill", uselist=False, lazy="raise")
    saved_views: Mapped[list["SavedView"]] = relationship(back_populates="skill", lazy="raise")


class SkillVersion(CreatedAtMixin, Base):
    __tablename__ = "skill_versions"
    __table_args__ = (
        CheckConstraint("version_number > 0", name="skill_versions_version_number_positive"),
        CheckConstraint(
            "version ~ '^(0|[1-9]\\d*)\\.(0|[1-9]\\d*)\\.(0|[1-9]\\d*)(?:-([0-9A-Za-z-]+(?:\\.[0-9A-Za-z-]+)*))?(?:\\+([0-9A-Za-z-]+(?:\\.[0-9A-Za-z-]+)*))?$'",
            name="skill_versions_version_semver_check",
        ),
        UniqueConstraint("skill_id", "version_number", name="skill_versions_skill_version_unique"),
        UniqueConstraint("skill_id", "version", name="skill_versions_skill_semver_unique"),
        UniqueConstraint("id", "skill_id", name="skill_versions_id_skill_unique"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    skill_id: Mapped[str] = mapped_column(Text, ForeignKey("skills.id"), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    version: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str | None] = mapped_column(Text)
    content_ref: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    content_digest: Mapped[str] = mapped_column(Text, nullable=False)
    change_summary: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str] = mapped_column(Text, nullable=False)

    skill: Mapped[Skill] = relationship(back_populates="versions", foreign_keys=[skill_id], lazy="raise")
    current_for_skill: Mapped[Skill | None] = relationship(
        primaryjoin=lambda: and_(
            foreign(Skill.current_version_id) == SkillVersion.id,
            Skill.id == SkillVersion.skill_id,
        ),
        back_populates="current_version",
        viewonly=True,
        uselist=False,
        lazy="raise",
    )
    eval_runs: Mapped[list["EvalRun"]] = relationship(back_populates="skill_version", overlaps="eval_set,runs", lazy="raise")
    review_requests: Mapped[list["ReviewRequest"]] = relationship(back_populates="skill_version", lazy="raise")
    workflow_sync: Mapped["WorkflowSync | None"] = relationship(back_populates="skill_version", uselist=False, lazy="raise")


class SkillTag(CreatedAtMixin, Base):
    __tablename__ = "skill_tags"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tag_group_id", "tag_value"],
            ["tag_values.tag_group_id", "tag_values.value"],
            name="skill_tags_tag_value_fkey",
        ),
    )

    skill_id: Mapped[str] = mapped_column(Text, ForeignKey("skills.id"), primary_key=True)
    tag_group_id: Mapped[str] = mapped_column(Text, primary_key=True)
    tag_value: Mapped[str] = mapped_column(Text, primary_key=True)
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
