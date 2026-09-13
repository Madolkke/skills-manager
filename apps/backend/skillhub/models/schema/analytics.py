"""运营事实独立保存，不随 Skill 永久删除而清理。"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Index, Text, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from skillhub.models.schema.base import Base


class SkillCreationFact(Base):
    __tablename__ = "skill_creation_facts"
    __table_args__ = (Index("skill_creation_facts_created_idx", "created_at"),)

    skill_id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    owner_ref: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))


class SkillVisitEvent(Base):
    __tablename__ = "skill_visit_events"
    __table_args__ = (
        Index("skill_visit_events_time_idx", "visited_at"),
        Index("skill_visit_events_skill_time_idx", "skill_id", "visited_at"),
    )

    event_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    skill_id: Mapped[str] = mapped_column(Text, nullable=False)
    actor: Mapped[str] = mapped_column(Text, nullable=False)
    visited_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))


class AnalyticsCollectionState(Base):
    __tablename__ = "analytics_collection_state"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    visits_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    creation_history_note: Mapped[str] = mapped_column(Text, nullable=False)
    demo_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
