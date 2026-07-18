from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Integer, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from skillhub.models.schema.base import Base, CreatedAtMixin, UpdatedAtMixin


class TagGroup(CreatedAtMixin, UpdatedAtMixin, Base):
    __tablename__ = "tag_groups"
    __table_args__ = (
        CheckConstraint("id ~ '^[A-Za-z0-9_-]+$'", name="tag_groups_id_format_check"),
        CheckConstraint("length(btrim(display_name)) > 0", name="tag_groups_display_name_non_empty"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    free_form: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    created_by: Mapped[str] = mapped_column(Text, nullable=False)

    values: Mapped[list["TagValue"]] = relationship(back_populates="group", lazy="raise")


class TagValue(CreatedAtMixin, UpdatedAtMixin, Base):
    __tablename__ = "tag_values"
    __table_args__ = (CheckConstraint("length(btrim(value)) > 0", name="tag_values_value_non_empty"),)

    tag_group_id: Mapped[str] = mapped_column(Text, ForeignKey("tag_groups.id"), primary_key=True)
    value: Mapped[str] = mapped_column(Text, primary_key=True)
    display_name: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    created_by: Mapped[str] = mapped_column(Text, nullable=False)

    group: Mapped[TagGroup] = relationship(back_populates="values", lazy="raise")


class TagGroupCascade(CreatedAtMixin, Base):
    __tablename__ = "tag_group_cascades"
    __table_args__ = (
        ForeignKeyConstraint(
            ["parent_tag_group_id", "parent_tag_value"],
            ["tag_values.tag_group_id", "tag_values.value"],
            name="tag_group_cascades_parent_value_fkey",
        ),
        CheckConstraint("child_tag_group_id <> parent_tag_group_id", name="tag_group_cascades_no_self_parent_check"),
    )

    child_tag_group_id: Mapped[str] = mapped_column(Text, ForeignKey("tag_groups.id"), primary_key=True)
    parent_tag_group_id: Mapped[str] = mapped_column(Text, nullable=False)
    parent_tag_value: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str] = mapped_column(Text, nullable=False)


class Group(CreatedAtMixin, UpdatedAtMixin, Base):
    __tablename__ = "groups"
    __table_args__ = (
        CheckConstraint("scope_type in ('global', 'skill')", name="groups_scope_type_check"),
        UniqueConstraint("scope_type", "scope_id", "name", name="groups_scope_name_unique"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    scope_type: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'global'"))
    scope_id: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'default'"))
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    created_by: Mapped[str] = mapped_column(Text, nullable=False)

    memberships: Mapped[list["GroupMembership"]] = relationship(back_populates="group", lazy="raise")


class GroupMembership(CreatedAtMixin, Base):
    __tablename__ = "group_memberships"
    __table_args__ = (CheckConstraint("subject_type in ('user')", name="group_memberships_subject_type_check"),)

    group_id: Mapped[str] = mapped_column(Text, ForeignKey("groups.id"), primary_key=True)
    subject_type: Mapped[str] = mapped_column(Text, primary_key=True)
    subject_id: Mapped[str] = mapped_column(Text, primary_key=True)
    created_by: Mapped[str] = mapped_column(Text, nullable=False)

    group: Mapped[Group] = relationship(back_populates="memberships", lazy="raise")


class RoleAssignment(CreatedAtMixin, Base):
    __tablename__ = "role_assignments"
    __table_args__ = (
        CheckConstraint("subject_type in ('user', 'group')", name="role_assignments_subject_type_check"),
        CheckConstraint("resource_type in ('skill', 'skill_tag')", name="role_assignments_resource_type_check"),
        CheckConstraint("role in ('admin', 'owner', 'maintainer', 'evaluator', 'reviewer', 'viewer')", name="role_assignments_role_check"),
        UniqueConstraint("subject_type", "subject_id", "resource_type", "resource_id", "role", name="role_assignments_scope_unique"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    subject_type: Mapped[str] = mapped_column(Text, nullable=False)
    subject_id: Mapped[str] = mapped_column(Text, nullable=False)
    resource_type: Mapped[str] = mapped_column(Text, nullable=False)
    resource_id: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str] = mapped_column(Text, nullable=False)


class Notification(CreatedAtMixin, Base):
    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    recipient_actor_id: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    resource_type: Mapped[str] = mapped_column(Text, nullable=False)
    resource_id: Mapped[str] = mapped_column(Text, nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[str] = mapped_column(Text, nullable=False)


class AuditEvent(CreatedAtMixin, Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    actor_ref: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    resource_type: Mapped[str] = mapped_column(Text, nullable=False)
    resource_id: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
