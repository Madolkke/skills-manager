from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import ARRAY, Boolean, CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Integer, Text, UniqueConstraint, and_, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, foreign, mapped_column, relationship

from skillhub.models.schema.base import Base, CreatedAtMixin, UpdatedAtMixin

if TYPE_CHECKING:
    from skillhub.models.schema.artifacts import Artifact
    from skillhub.models.schema.runtime import Job
    from skillhub.models.schema.skills import Skill, SkillVersion


class EvalSet(CreatedAtMixin, UpdatedAtMixin, Base):
    __tablename__ = "eval_sets"
    __table_args__ = (
        UniqueConstraint("id", "skill_id", name="eval_sets_id_skill_unique"),
        UniqueConstraint("skill_id", "name", name="eval_sets_skill_name_unique"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    skill_id: Mapped[str] = mapped_column(Text, ForeignKey("skills.id"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))

    skill: Mapped["Skill"] = relationship(back_populates="eval_sets", lazy="raise")
    case_links: Mapped[list["EvalSetCase"]] = relationship(back_populates="eval_set", overlaps="case,set_links", lazy="raise")
    runs: Mapped[list["EvalRun"]] = relationship(back_populates="eval_set", lazy="raise")


class EvalCase(CreatedAtMixin, UpdatedAtMixin, Base):
    __tablename__ = "eval_cases"
    __table_args__ = (
        UniqueConstraint("id", "skill_id", name="eval_cases_id_skill_unique"),
        ForeignKeyConstraint(
            ["current_version_id", "skill_id"],
            ["eval_case_versions.id", "eval_case_versions.skill_id"],
            name="eval_cases_current_version_fkey",
            use_alter=True,
        ),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    skill_id: Mapped[str] = mapped_column(Text, ForeignKey("skills.id"), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    current_version_id: Mapped[str | None] = mapped_column(Text)

    skill: Mapped["Skill"] = relationship(back_populates="eval_cases", foreign_keys=[skill_id], lazy="raise")
    versions: Mapped[list["EvalCaseVersion"]] = relationship(
        back_populates="case",
        foreign_keys="EvalCaseVersion.case_id",
        lazy="raise",
    )
    current_version: Mapped["EvalCaseVersion | None"] = relationship(
        primaryjoin=lambda: and_(
            foreign(EvalCase.current_version_id) == EvalCaseVersion.id,
            EvalCase.skill_id == EvalCaseVersion.skill_id,
        ),
        back_populates="current_for_case",
        viewonly=True,
        lazy="raise",
    )
    set_links: Mapped[list["EvalSetCase"]] = relationship(back_populates="case", overlaps="case_links,eval_set", lazy="raise")


class EvalCaseVersion(CreatedAtMixin, Base):
    __tablename__ = "eval_case_versions"
    __table_args__ = (
        CheckConstraint("jsonb_typeof(steps) = 'array'", name="eval_case_versions_steps_array"),
        CheckConstraint("jsonb_typeof(runner_config) = 'object'", name="eval_case_versions_runner_config_object"),
        CheckConstraint("version_number > 0", name="eval_case_versions_version_number_positive"),
        UniqueConstraint("case_id", "version_number", name="eval_case_versions_case_version_unique"),
        UniqueConstraint("id", "skill_id", name="eval_case_versions_id_skill_unique"),
        ForeignKeyConstraint(
            ["case_id", "skill_id"],
            ["eval_cases.id", "eval_cases.skill_id"],
            name="eval_case_versions_case_skill_fkey",
        ),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    skill_id: Mapped[str] = mapped_column(Text, nullable=False)
    case_id: Mapped[str] = mapped_column(Text, nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    workspace_artifact_id: Mapped[str | None] = mapped_column(Text, ForeignKey("artifacts.id"))
    steps: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    runner_config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    notes: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(Text, nullable=False)

    case: Mapped[EvalCase] = relationship(back_populates="versions", foreign_keys=[case_id], lazy="raise")
    current_for_case: Mapped[EvalCase | None] = relationship(
        primaryjoin=lambda: and_(
            foreign(EvalCase.current_version_id) == EvalCaseVersion.id,
            EvalCase.skill_id == EvalCaseVersion.skill_id,
        ),
        back_populates="current_version",
        viewonly=True,
        uselist=False,
        lazy="raise",
    )
    workspace_artifact: Mapped["Artifact | None"] = relationship(back_populates="eval_case_versions", lazy="raise")
    case_results: Mapped[list["CaseResult"]] = relationship(back_populates="case_version", lazy="raise")


class EvalSetCase(Base):
    __tablename__ = "eval_set_cases"
    __table_args__ = (
        CheckConstraint("position >= 0", name="eval_set_cases_position_non_negative"),
        UniqueConstraint("eval_set_id", "case_id", name="eval_set_cases_case_unique"),
        ForeignKeyConstraint(
            ["eval_set_id", "skill_id"],
            ["eval_sets.id", "eval_sets.skill_id"],
            name="eval_set_cases_set_skill_fkey",
        ),
        ForeignKeyConstraint(
            ["case_id", "skill_id"],
            ["eval_cases.id", "eval_cases.skill_id"],
            name="eval_set_cases_case_skill_fkey",
        ),
    )

    eval_set_id: Mapped[str] = mapped_column(Text, primary_key=True)
    skill_id: Mapped[str] = mapped_column(Text, nullable=False)
    case_id: Mapped[str] = mapped_column(Text, nullable=False)
    position: Mapped[int] = mapped_column(Integer, primary_key=True)

    eval_set: Mapped[EvalSet] = relationship(back_populates="case_links", foreign_keys=[eval_set_id], overlaps="case,set_links", lazy="raise")
    case: Mapped[EvalCase] = relationship(back_populates="set_links", foreign_keys=[case_id], overlaps="case_links,eval_set", lazy="raise")


class EvalRun(CreatedAtMixin, Base):
    __tablename__ = "eval_runs"
    __table_args__ = (
        CheckConstraint("status in ('queued', 'running', 'finished', 'failed')", name="eval_runs_status_check"),
        UniqueConstraint("id", "skill_id", name="eval_runs_id_skill_unique"),
        ForeignKeyConstraint(
            ["skill_version_id", "skill_id"],
            ["skill_versions.id", "skill_versions.skill_id"],
            name="eval_runs_skill_version_skill_fkey",
        ),
        ForeignKeyConstraint(
            ["eval_set_id", "skill_id"],
            ["eval_sets.id", "eval_sets.skill_id"],
            name="eval_runs_eval_set_skill_fkey",
        ),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    skill_id: Mapped[str] = mapped_column(Text, nullable=False)
    skill_version_id: Mapped[str] = mapped_column(Text, nullable=False)
    eval_set_id: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    environment_tags: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default=text("'{}'"))
    run_context: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    run_context_hash: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    result_artifact_id: Mapped[str | None] = mapped_column(Text, ForeignKey("artifacts.id"))
    created_by: Mapped[str] = mapped_column(Text, nullable=False)

    skill_version: Mapped["SkillVersion"] = relationship(back_populates="eval_runs", foreign_keys=[skill_version_id], lazy="raise")
    eval_set: Mapped[EvalSet] = relationship(back_populates="runs", foreign_keys=[eval_set_id], overlaps="eval_runs,skill_version", lazy="raise")
    case_results: Mapped[list["CaseResult"]] = relationship(back_populates="run", overlaps="case_results", lazy="raise")


class CaseResult(CreatedAtMixin, Base):
    __tablename__ = "case_results"
    __table_args__ = (
        CheckConstraint("score in (0, 1)", name="case_results_score_pass_fail"),
        ForeignKeyConstraint(["run_id", "skill_id"], ["eval_runs.id", "eval_runs.skill_id"], name="case_results_run_skill_fkey"),
        ForeignKeyConstraint(
            ["case_version_id", "skill_id"],
            ["eval_case_versions.id", "eval_case_versions.skill_id"],
            name="case_results_case_skill_fkey",
        ),
    )

    run_id: Mapped[str] = mapped_column(Text, primary_key=True)
    skill_id: Mapped[str] = mapped_column(Text, nullable=False)
    case_version_id: Mapped[str] = mapped_column(Text, primary_key=True)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    result_artifact_id: Mapped[str | None] = mapped_column(Text, ForeignKey("artifacts.id"))

    run: Mapped[EvalRun] = relationship(back_populates="case_results", foreign_keys=[run_id], lazy="raise")
    case_version: Mapped[EvalCaseVersion] = relationship(back_populates="case_results", foreign_keys=[case_version_id], lazy="raise")


class EvalCaseRun(CreatedAtMixin, Base):
    __tablename__ = "eval_case_runs"
    __table_args__ = (
        CheckConstraint("status in ('queued', 'running', 'succeeded', 'failed', 'canceled')", name="eval_case_runs_status_check"),
        CheckConstraint("score is null or score in (0, 1)", name="eval_case_runs_score_pass_fail"),
        UniqueConstraint("id", "skill_id", name="eval_case_runs_id_skill_unique"),
        ForeignKeyConstraint(["skill_version_id", "skill_id"], ["skill_versions.id", "skill_versions.skill_id"], name="eval_case_runs_skill_version_skill_fkey"),
        ForeignKeyConstraint(["eval_set_id", "skill_id"], ["eval_sets.id", "eval_sets.skill_id"], name="eval_case_runs_eval_set_skill_fkey"),
        ForeignKeyConstraint(["case_version_id", "skill_id"], ["eval_case_versions.id", "eval_case_versions.skill_id"], name="eval_case_runs_case_skill_fkey"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    job_id: Mapped[str | None] = mapped_column(Text, ForeignKey("jobs.id"))
    skill_id: Mapped[str] = mapped_column(Text, nullable=False)
    skill_version_id: Mapped[str] = mapped_column(Text, nullable=False)
    eval_set_id: Mapped[str] = mapped_column(Text, nullable=False)
    case_version_id: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    environment_tags: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default=text("'{}'"))
    run_context: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    run_context_hash: Mapped[str] = mapped_column(Text, nullable=False)
    passed: Mapped[bool | None] = mapped_column(Boolean)
    score: Mapped[int | None] = mapped_column(Integer)
    result_artifact_id: Mapped[str | None] = mapped_column(Text, ForeignKey("artifacts.id"))
    runner_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    error: Mapped[str | None] = mapped_column(Text)

    job: Mapped["Job | None"] = relationship(back_populates="eval_case_runs", lazy="raise")


class AcceptedVerification(CreatedAtMixin, Base):
    __tablename__ = "accepted_verifications"
    __table_args__ = (
        UniqueConstraint("id", "skill_id", name="accepted_verifications_id_skill_unique"),
        UniqueConstraint("skill_id", "skill_version_id", "eval_set_id", "run_context_hash", name="accepted_verifications_context_unique"),
        ForeignKeyConstraint(["skill_version_id", "skill_id"], ["skill_versions.id", "skill_versions.skill_id"], name="accepted_verifications_skill_version_skill_fkey"),
        ForeignKeyConstraint(["eval_set_id", "skill_id"], ["eval_sets.id", "eval_sets.skill_id"], name="accepted_verifications_eval_set_skill_fkey"),
        ForeignKeyConstraint(["eval_run_id", "skill_id"], ["eval_runs.id", "eval_runs.skill_id"], name="accepted_verifications_eval_run_skill_fkey"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    skill_id: Mapped[str] = mapped_column(Text, nullable=False)
    skill_version_id: Mapped[str] = mapped_column(Text, nullable=False)
    eval_set_id: Mapped[str] = mapped_column(Text, nullable=False)
    run_context_hash: Mapped[str] = mapped_column(Text, nullable=False)
    eval_run_id: Mapped[str] = mapped_column(Text, nullable=False)
    note: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
