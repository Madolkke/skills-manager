from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from skillhub.models.schema.base import Base, CreatedAtMixin, UpdatedAtMixin


class WorkflowAgentSession(CreatedAtMixin, UpdatedAtMixin, Base):
    __tablename__ = "workflow_agent_sessions"
    __table_args__ = (
        CheckConstraint("status in ('active', 'archived')", name="workflow_agent_sessions_status_check"),
        CheckConstraint("jsonb_typeof(agentscope_sessions) = 'object'", name="workflow_agent_sessions_scope_map_object"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    skill_id: Mapped[str] = mapped_column(Text, ForeignKey("skills.id", ondelete="CASCADE"), nullable=False)
    actor_ref: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'active'"))
    agentscope_sessions: Mapped[dict[str, str]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))


class WorkflowAgentRun(CreatedAtMixin, UpdatedAtMixin, Base):
    __tablename__ = "workflow_agent_runs"
    __table_args__ = (
        CheckConstraint(
            "status in ('starting', 'running', 'completed', 'failed', 'canceled', 'interrupted')",
            name="workflow_agent_runs_status_check",
        ),
        CheckConstraint("base_revision > 0", name="workflow_agent_runs_revision_positive"),
        CheckConstraint("jsonb_typeof(selection) = 'object'", name="workflow_agent_runs_selection_object"),
        CheckConstraint("jsonb_typeof(context_snapshot) = 'object'", name="workflow_agent_runs_context_object"),
        CheckConstraint("jsonb_typeof(usage) = 'object'", name="workflow_agent_runs_usage_object"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    session_id: Mapped[str] = mapped_column(Text, ForeignKey("workflow_agent_sessions.id", ondelete="CASCADE"), nullable=False)
    skill_id: Mapped[str] = mapped_column(Text, ForeignKey("skills.id", ondelete="CASCADE"), nullable=False)
    agent_id: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'starting'"))
    user_input: Mapped[str] = mapped_column(Text, nullable=False)
    response_text: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    selection: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    context_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    base_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    base_workflow_digest: Mapped[str] = mapped_column(Text, nullable=False)
    draft_digest: Mapped[str] = mapped_column(Text, nullable=False)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    usage: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    error: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class WorkflowAgentEvent(CreatedAtMixin, Base):
    __tablename__ = "workflow_agent_events"
    __table_args__ = (
        CheckConstraint("sequence > 0", name="workflow_agent_events_sequence_positive"),
        CheckConstraint("jsonb_typeof(payload) = 'object'", name="workflow_agent_events_payload_object"),
        UniqueConstraint("run_id", "sequence", name="workflow_agent_events_run_sequence_unique"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    run_id: Mapped[str] = mapped_column(Text, ForeignKey("workflow_agent_runs.id", ondelete="CASCADE"), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    native_event_id: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class WorkflowAgentProposal(CreatedAtMixin, UpdatedAtMixin, Base):
    __tablename__ = "workflow_agent_proposals"
    __table_args__ = (
        CheckConstraint("kind in ('debug_case_draft')", name="workflow_agent_proposals_kind_check"),
        CheckConstraint("status in ('proposed', 'applied', 'stale')", name="workflow_agent_proposals_status_check"),
        CheckConstraint("jsonb_typeof(payload) = 'object'", name="workflow_agent_proposals_payload_object"),
        CheckConstraint("jsonb_typeof(applied_result) = 'object'", name="workflow_agent_proposals_result_object"),
        UniqueConstraint("run_id", name="workflow_agent_proposals_run_unique"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    run_id: Mapped[str] = mapped_column(Text, ForeignKey("workflow_agent_runs.id", ondelete="CASCADE"), nullable=False)
    skill_id: Mapped[str] = mapped_column(Text, ForeignKey("skills.id", ondelete="CASCADE"), nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'proposed'"))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    base_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    base_workflow_digest: Mapped[str] = mapped_column(Text, nullable=False)
    draft_digest: Mapped[str] = mapped_column(Text, nullable=False)
    applied_result: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_by: Mapped[str] = mapped_column(Text, nullable=False)


__all__ = ["WorkflowAgentEvent", "WorkflowAgentProposal", "WorkflowAgentRun", "WorkflowAgentSession"]
