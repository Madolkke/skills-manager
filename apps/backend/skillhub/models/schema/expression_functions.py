from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, Boolean, CheckConstraint, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from skillhub.models.schema.base import Base, CreatedAtMixin, UpdatedAtMixin

_JSON = JSONB().with_variant(JSON, "sqlite")


class ExpressionFunction(CreatedAtMixin, UpdatedAtMixin, Base):
    """Persisted expression metadata. The body is documentation only and is never executed."""

    __tablename__ = "expression_functions"
    __table_args__ = (
        UniqueConstraint("name", name="expression_functions_name_unique"),
        CheckConstraint("length(trim(name)) > 0", name="expression_functions_name_nonempty"),
        CheckConstraint("length(trim(body)) > 0", name="expression_functions_body_nonempty"),
        CheckConstraint("length(trim(language)) > 0", name="expression_functions_language_nonempty"),
        CheckConstraint("jsonb_typeof(parameter_schema) = 'object'", name="expression_functions_parameter_schema_object"),
        CheckConstraint("jsonb_typeof(return_schema) = 'object'", name="expression_functions_return_schema_object"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    parameter_schema: Mapped[dict[str, Any]] = mapped_column(_JSON, nullable=False, server_default=text("'{}'::jsonb"))
    return_schema: Mapped[dict[str, Any]] = mapped_column(_JSON, nullable=False, server_default=text("'{}'::jsonb"))
    body: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'python'"))
    is_builtin: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    updated_by: Mapped[str] = mapped_column(Text, nullable=False)
