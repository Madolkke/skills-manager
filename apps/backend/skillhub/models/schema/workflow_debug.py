from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from skillhub.models.schema.base import Base, CreatedAtMixin, UpdatedAtMixin


class WorkflowDebugCase(CreatedAtMixin, UpdatedAtMixin, Base):
    __tablename__ = "workflow_debug_cases"
    __table_args__ = (
        CheckConstraint("length(btrim(name)) > 0", name="workflow_debug_cases_name_length_check"),
        CheckConstraint("jsonb_typeof(workflow_inputs) = 'object'", name="workflow_debug_cases_inputs_object"),
        CheckConstraint("jsonb_typeof(collection_fixtures) = 'object'", name="workflow_debug_cases_fixtures_object"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    skill_id: Mapped[str] = mapped_column(Text, ForeignKey("skills.id", ondelete="CASCADE"), nullable=False)
    step_id: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    expected_target_id: Mapped[str] = mapped_column(Text, nullable=False)
    workflow_inputs: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    collection_fixtures: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    updated_by: Mapped[str] = mapped_column(Text, nullable=False)


class WorkflowDebugRun(CreatedAtMixin, UpdatedAtMixin, Base):
    __tablename__ = "workflow_debug_runs"
    __table_args__ = (
        CheckConstraint("workflow_revision > 0", name="workflow_debug_runs_revision_positive"),
        CheckConstraint(
            "status in ('starting', 'running', 'paused', 'completed', 'failed', 'external_state_unknown')",
            name="workflow_debug_runs_status_check",
        ),
        CheckConstraint("jsonb_typeof(case_snapshot) = 'object'", name="workflow_debug_runs_snapshot_object"),
        CheckConstraint("jsonb_typeof(executor_identity) = 'object'", name="workflow_debug_runs_identity_object"),
        CheckConstraint("jsonb_typeof(resumed_pauses) = 'array'", name="workflow_debug_runs_pauses_array"),
        UniqueConstraint("task_id", name="workflow_debug_runs_task_id_unique"),
        UniqueConstraint("executor_run_id", name="workflow_debug_runs_executor_run_id_unique"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    case_id: Mapped[str] = mapped_column(Text, ForeignKey("workflow_debug_cases.id", ondelete="CASCADE"), nullable=False)
    skill_id: Mapped[str] = mapped_column(Text, ForeignKey("skills.id", ondelete="CASCADE"), nullable=False)
    step_id: Mapped[str] = mapped_column(Text, nullable=False)
    expected_target_id: Mapped[str] = mapped_column(Text, nullable=False)
    case_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    workflow_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    workflow_digest: Mapped[str] = mapped_column(Text, nullable=False)
    task_id: Mapped[str] = mapped_column(Text, nullable=False)
    executor_run_id: Mapped[str | None] = mapped_column(Text)
    executor_identity: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    passed: Mapped[bool | None] = mapped_column(Boolean)
    executor_status: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    error: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    resumed_pauses: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


__all__ = ["WorkflowDebugCase", "WorkflowDebugRun"]
