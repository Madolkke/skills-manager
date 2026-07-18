from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from skillhub.models.schema.base import Base, CreatedAtMixin, UpdatedAtMixin

if TYPE_CHECKING:
    from skillhub.models.schema.evaluations import EvalCaseRun


class Job(CreatedAtMixin, Base):
    __tablename__ = "jobs"
    __table_args__ = (
        CheckConstraint("status in ('queued', 'running', 'succeeded', 'failed', 'canceled')", name="jobs_status_check"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    type: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'queued'"))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    result_ref: Mapped[str | None] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    locked_by: Mapped[str | None] = mapped_column(Text)
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    error: Mapped[str | None] = mapped_column(Text)

    eval_case_runs: Mapped[list["EvalCaseRun"]] = relationship(back_populates="job", lazy="raise")
    builder_messages: Mapped[list["SkillBuilderMessage"]] = relationship(back_populates="job", lazy="raise")


class WorkerHeartbeat(Base):
    __tablename__ = "worker_heartbeats"
    __table_args__ = (CheckConstraint("status in ('idle', 'running')", name="worker_heartbeats_status_check"),)

    worker_id: Mapped[str] = mapped_column(Text, primary_key=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'idle'"))
    current_job_id: Mapped[str | None] = mapped_column(Text)
    current_job_type: Mapped[str | None] = mapped_column(Text)
    current_run_id: Mapped[str | None] = mapped_column(Text)
    current_session_id: Mapped[str | None] = mapped_column(Text)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    metadata_payload: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )


class OpencodeAgent(CreatedAtMixin, UpdatedAtMixin, Base):
    __tablename__ = "opencode_agents"
    __table_args__ = (
        CheckConstraint("id ~ '^[A-Za-z0-9_-]+$'", name="opencode_agents_id_format_check"),
        CheckConstraint("length(btrim(name)) > 0", name="opencode_agents_name_non_empty"),
        CheckConstraint("length(btrim(prompt)) > 0", name="opencode_agents_prompt_non_empty"),
        CheckConstraint("jsonb_typeof(permission) = 'object'", name="opencode_agents_permission_object"),
        CheckConstraint("jsonb_typeof(steps) = 'array'", name="opencode_agents_steps_array"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    permission: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    provider_id: Mapped[str | None] = mapped_column(Text)
    model_id: Mapped[str | None] = mapped_column(Text)
    temperature: Mapped[str | None] = mapped_column(Text)
    steps: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    updated_by: Mapped[str] = mapped_column(Text, nullable=False)


class SkillBuilderSession(CreatedAtMixin, UpdatedAtMixin, Base):
    __tablename__ = "skill_builder_sessions"
    __table_args__ = (
        CheckConstraint("status in ('active', 'running', 'draft_ready', 'created', 'failed')", name="skill_builder_sessions_status_check"),
        CheckConstraint("jsonb_typeof(draft_files) = 'array'", name="skill_builder_sessions_draft_files_array"),
        CheckConstraint("jsonb_typeof(run_selection) = 'object'", name="skill_builder_sessions_run_selection_object"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    actor_ref: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'active'"))
    opencode_session_id: Mapped[str | None] = mapped_column(Text)
    workdir: Mapped[str | None] = mapped_column(Text)
    draft_files: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    run_selection: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_skill_id: Mapped[str | None] = mapped_column(Text, ForeignKey("skills.id"))
    created_skill_version_id: Mapped[str | None] = mapped_column(Text, ForeignKey("skill_versions.id"))
    last_error: Mapped[str | None] = mapped_column(Text)

    messages: Mapped[list["SkillBuilderMessage"]] = relationship(back_populates="session", lazy="raise")


class SkillBuilderMessage(CreatedAtMixin, Base):
    __tablename__ = "skill_builder_messages"
    __table_args__ = (
        CheckConstraint("role in ('user', 'assistant', 'system')", name="skill_builder_messages_role_check"),
        CheckConstraint("intent in ('chat', 'generate_draft')", name="skill_builder_messages_intent_check"),
        CheckConstraint("jsonb_typeof(metadata) = 'object'", name="skill_builder_messages_metadata_object"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    session_id: Mapped[str] = mapped_column(Text, ForeignKey("skill_builder_sessions.id"), nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    intent: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'chat'"))
    content: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    metadata_payload: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    job_id: Mapped[str | None] = mapped_column(Text, ForeignKey("jobs.id"))

    session: Mapped[SkillBuilderSession] = relationship(back_populates="messages", lazy="raise")
    job: Mapped[Job | None] = relationship(back_populates="builder_messages", lazy="raise")
