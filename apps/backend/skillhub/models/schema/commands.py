from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, Boolean, CheckConstraint, ForeignKey, Integer, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from skillhub.models.schema.base import Base, CreatedAtMixin, UpdatedAtMixin

_JSON = JSONB().with_variant(JSON, "sqlite")


class SystemCommandLibraryEntry(CreatedAtMixin, UpdatedAtMixin, Base):
    """Administrator-managed command templates shared by all users."""

    __tablename__ = "system_command_library_entries"
    __table_args__ = (
        UniqueConstraint("key", name="system_command_library_entries_key_unique"),
        UniqueConstraint("normalized_expression", name="system_command_library_entries_normalized_expression_unique"),
        CheckConstraint("length(trim(key)) > 0", name="system_command_library_entries_key_nonempty"),
        CheckConstraint("length(trim(name)) > 0", name="system_command_library_entries_name_nonempty"),
        CheckConstraint("length(trim(expression)) > 0", name="system_command_library_entries_expression_nonempty"),
        CheckConstraint("length(trim(normalized_expression)) > 0", name="system_command_library_entries_normalized_expression_nonempty"),
        CheckConstraint("jsonb_typeof(metadata) = 'object'", name="system_command_library_entries_metadata_object"),
        CheckConstraint("jsonb_typeof(captures) = 'object'", name="system_command_library_entries_captures_object"),
        CheckConstraint("jsonb_typeof(document) = 'object'", name="system_command_library_entries_document_object"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    key: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    expression: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_expression: Mapped[str] = mapped_column(Text, nullable=False)
    captures: Mapped[dict[str, Any]] = mapped_column(_JSON, nullable=False, server_default=text("'{}'::jsonb"))
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata", _JSON, nullable=False, server_default=text("'{}'::jsonb")
    )
    document: Mapped[dict[str, Any]] = mapped_column(_JSON, nullable=False, server_default=text("'{}'::jsonb"))
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    updated_by: Mapped[str] = mapped_column(Text, nullable=False)

    user_entries: Mapped[list["UserCommandLibraryEntry"]] = relationship(
        back_populates="source_system_command", lazy="raise"
    )


class UserCommandLibraryEntry(CreatedAtMixin, UpdatedAtMixin, Base):
    """A user's editable copy of a command template."""

    __tablename__ = "user_command_library_entries"
    __table_args__ = (
        UniqueConstraint("workflow_id", "collection_id", name="user_command_library_entries_workflow_collection_unique"),
        CheckConstraint("length(trim(owner_ref)) > 0", name="user_command_library_entries_owner_nonempty"),
        CheckConstraint("length(trim(key)) > 0", name="user_command_library_entries_key_nonempty"),
        CheckConstraint("length(trim(name)) > 0", name="user_command_library_entries_name_nonempty"),
        CheckConstraint("length(trim(expression)) > 0", name="user_command_library_entries_expression_nonempty"),
        CheckConstraint("length(trim(normalized_expression)) > 0", name="user_command_library_entries_normalized_expression_nonempty"),
        CheckConstraint("jsonb_typeof(metadata) = 'object'", name="user_command_library_entries_metadata_object"),
        CheckConstraint("jsonb_typeof(captures) = 'object'", name="user_command_library_entries_captures_object"),
        CheckConstraint("jsonb_typeof(document) = 'object'", name="user_command_library_entries_document_object"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    owner_ref: Mapped[str] = mapped_column(Text, nullable=False)
    workflow_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("workflows.id", name="user_command_library_entries_workflow_fk", ondelete="CASCADE"),
        nullable=False,
    )
    collection_id: Mapped[str] = mapped_column(Text, nullable=False)
    key: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    expression: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_expression: Mapped[str] = mapped_column(Text, nullable=False)
    captures: Mapped[dict[str, Any]] = mapped_column(_JSON, nullable=False, server_default=text("'{}'::jsonb"))
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata", _JSON, nullable=False, server_default=text("'{}'::jsonb")
    )
    document: Mapped[dict[str, Any]] = mapped_column(_JSON, nullable=False, server_default=text("'{}'::jsonb"))
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    source_system_command_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey(
            "system_command_library_entries.id",
            name="user_command_library_entries_source_system_command_fk",
            ondelete="RESTRICT",
        ),
        nullable=True,
    )
    collection_definition_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    collection_revision: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    updated_by: Mapped[str] = mapped_column(Text, nullable=False)

    source_system_command: Mapped[SystemCommandLibraryEntry | None] = relationship(
        back_populates="user_entries", lazy="raise"
    )


SystemCommand = SystemCommandLibraryEntry
UserCommand = UserCommandLibraryEntry


__all__ = [
    "SystemCommand",
    "SystemCommandLibraryEntry",
    "UserCommand",
    "UserCommandLibraryEntry",
]
