from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Integer, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from skillhub.models.schema.base import Base, CreatedAtMixin, UpdatedAtMixin

if TYPE_CHECKING:
    from skillhub.models.schema.skills import SkillVersion


class ReviewRequest(CreatedAtMixin, Base):
    __tablename__ = "review_requests"
    __table_args__ = (
        CheckConstraint("status in ('open', 'closed', 'cancelled')", name="review_requests_status_check"),
        UniqueConstraint("id", "skill_id", name="review_requests_id_skill_unique"),
        ForeignKeyConstraint(
            ["skill_version_id", "skill_id"],
            ["skill_versions.id", "skill_versions.skill_id"],
            name="review_requests_skill_version_skill_fkey",
        ),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    skill_id: Mapped[str] = mapped_column(Text, nullable=False)
    skill_version_id: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_by: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(Text, nullable=False)

    skill_version: Mapped["SkillVersion"] = relationship(back_populates="review_requests", lazy="raise")
    reviewers: Mapped[list["ReviewRequestReviewer"]] = relationship(back_populates="review", lazy="raise")
    responses: Mapped[list["ReviewResponse"]] = relationship(back_populates="review", overlaps="response,reviewer", lazy="raise")
    publish_targets: Mapped[list["ReviewRequestPublishTarget"]] = relationship(back_populates="review", lazy="raise")
    check_results: Mapped[list["ReviewCheckResult"]] = relationship(back_populates="review", lazy="raise")
    publish_records: Mapped[list["PublishRecord"]] = relationship(back_populates="review", lazy="raise")


class ReviewRequestReviewer(CreatedAtMixin, Base):
    __tablename__ = "review_request_reviewers"
    __table_args__ = (
        CheckConstraint("source_subject_type in ('user', 'group')", name="review_request_reviewers_source_type_check"),
        ForeignKeyConstraint(
            ["review_request_id", "skill_id"],
            ["review_requests.id", "review_requests.skill_id"],
            name="review_request_reviewers_review_skill_fkey",
        ),
    )

    review_request_id: Mapped[str] = mapped_column(Text, primary_key=True)
    skill_id: Mapped[str] = mapped_column(Text, nullable=False)
    reviewer_actor: Mapped[str] = mapped_column(Text, primary_key=True)
    source_subject_type: Mapped[str] = mapped_column(Text, nullable=False)
    source_subject_id: Mapped[str] = mapped_column(Text, nullable=False)

    review: Mapped[ReviewRequest] = relationship(back_populates="reviewers", foreign_keys=[review_request_id], lazy="raise")
    response: Mapped["ReviewResponse | None"] = relationship(back_populates="reviewer", overlaps="responses,review", uselist=False, lazy="raise")


class ReviewResponse(CreatedAtMixin, UpdatedAtMixin, Base):
    __tablename__ = "review_responses"
    __table_args__ = (
        CheckConstraint("score in (-1, 0, 1)", name="review_responses_score_check"),
        ForeignKeyConstraint(
            ["review_request_id", "skill_id"],
            ["review_requests.id", "review_requests.skill_id"],
            name="review_responses_review_skill_fkey",
        ),
        ForeignKeyConstraint(
            ["review_request_id", "reviewer_actor"],
            ["review_request_reviewers.review_request_id", "review_request_reviewers.reviewer_actor"],
            name="review_responses_reviewer_fkey",
        ),
    )

    review_request_id: Mapped[str] = mapped_column(Text, primary_key=True)
    skill_id: Mapped[str] = mapped_column(Text, nullable=False)
    reviewer_actor: Mapped[str] = mapped_column(Text, primary_key=True)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))

    review: Mapped[ReviewRequest] = relationship(back_populates="responses", foreign_keys=[review_request_id], overlaps="response,reviewer", lazy="raise")
    reviewer: Mapped[ReviewRequestReviewer] = relationship(back_populates="response", overlaps="responses,review", lazy="raise")


class PublishTarget(CreatedAtMixin, UpdatedAtMixin, Base):
    __tablename__ = "publish_targets"
    __table_args__ = (
        UniqueConstraint("target_key", name="publish_targets_key_unique"),
        CheckConstraint("length(btrim(target_key)) > 0", name="publish_targets_key_non_empty"),
        CheckConstraint("jsonb_typeof(gate_expression) = 'object'", name="publish_targets_gate_expression_object"),
        CheckConstraint("jsonb_typeof(config) = 'object'", name="publish_targets_config_object"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    target_key: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    auto_publish_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    gate_expression: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_by: Mapped[str] = mapped_column(Text, nullable=False)

    review_links: Mapped[list["ReviewRequestPublishTarget"]] = relationship(back_populates="publish_target", lazy="raise")
    publish_records: Mapped[list["PublishRecord"]] = relationship(back_populates="publish_target", lazy="raise")


class ReviewRequestPublishTarget(CreatedAtMixin, Base):
    __tablename__ = "review_request_publish_targets"
    __table_args__ = (
        ForeignKeyConstraint(
            ["review_request_id", "skill_id"],
            ["review_requests.id", "review_requests.skill_id"],
            name="review_request_publish_targets_review_skill_fkey",
        ),
    )

    review_request_id: Mapped[str] = mapped_column(Text, primary_key=True)
    skill_id: Mapped[str] = mapped_column(Text, nullable=False)
    publish_target_id: Mapped[str] = mapped_column(Text, ForeignKey("publish_targets.id"), primary_key=True)
    auto_submit_on_pass: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))

    review: Mapped[ReviewRequest] = relationship(back_populates="publish_targets", foreign_keys=[review_request_id], lazy="raise")
    publish_target: Mapped[PublishTarget] = relationship(back_populates="review_links", lazy="raise")


class ReviewCheckResult(CreatedAtMixin, Base):
    __tablename__ = "review_check_results"
    __table_args__ = (
        ForeignKeyConstraint(
            ["review_request_id", "skill_id"],
            ["review_requests.id", "review_requests.skill_id"],
            name="review_check_results_review_skill_fkey",
        ),
    )

    review_request_id: Mapped[str] = mapped_column(Text, primary_key=True)
    skill_id: Mapped[str] = mapped_column(Text, nullable=False)
    check_id: Mapped[str] = mapped_column(Text, primary_key=True)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))

    review: Mapped[ReviewRequest] = relationship(back_populates="check_results", foreign_keys=[review_request_id], lazy="raise")


class PublishRecord(CreatedAtMixin, Base):
    __tablename__ = "publish_records"
    __table_args__ = (
        CheckConstraint(
            "status in ('pending_confirmation', 'queued', 'releasing', 'released', 'cancelled', 'failed')",
            name="publish_records_status_check",
        ),
        UniqueConstraint("skill_version_id", "publish_target_id", name="publish_records_version_target_unique"),
        UniqueConstraint("id", "skill_id", name="publish_records_id_skill_unique"),
        ForeignKeyConstraint(["skill_version_id", "skill_id"], ["skill_versions.id", "skill_versions.skill_id"], name="publish_records_skill_version_skill_fkey"),
        ForeignKeyConstraint(["review_request_id", "skill_id"], ["review_requests.id", "review_requests.skill_id"], name="publish_records_review_skill_fkey"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    skill_id: Mapped[str] = mapped_column(Text, nullable=False)
    skill_version_id: Mapped[str] = mapped_column(Text, nullable=False)
    review_request_id: Mapped[str] = mapped_column(Text, nullable=False)
    publish_target_id: Mapped[str] = mapped_column(Text, ForeignKey("publish_targets.id"), nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    check_snapshot: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    metadata_payload: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    confirmed_by: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(Text, nullable=False)

    review: Mapped[ReviewRequest] = relationship(back_populates="publish_records", foreign_keys=[review_request_id], lazy="raise")
    publish_target: Mapped[PublishTarget] = relationship(back_populates="publish_records", lazy="raise")
