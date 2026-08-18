from __future__ import annotations

from typing import Annotated, Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class CommandSearchPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    command: Annotated[str, Field(default="", max_length=4000, validation_alias=AliasChoices("command", "query"))]
    owner_ref: str | None = Field(default=None, alias="ownerRef")
    include_system: bool = Field(default=True, alias="includeSystem")
    include_user: bool = Field(default=False, alias="includeUser")
    include_disabled: bool = Field(default=False, alias="includeDisabled")
    partial: bool = True
    prefix: bool = True
    target_version: Annotated[str, Field(max_length=200)] | None = Field(default=None, alias="targetVersion")


class SystemCommandPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: str | None = None
    key: Annotated[str, Field(min_length=1, max_length=160)]
    expression: str = Field(
        min_length=1,
        max_length=4000,
        validation_alias=AliasChoices("expression", "command", "commandTemplate", "command_template"),
    )
    name: str | None = None
    description: str = ""
    captures: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    samples: list[dict[str, Any]] = Field(default_factory=list)
    output_schema: dict[str, Any] = Field(
        default_factory=lambda: {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
        alias="outputSchema",
    )
    ttp: Annotated[str, Field(max_length=50000)] = ""
    enabled: bool = True


class SystemCommandUpdatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    key: Annotated[str, Field(min_length=1, max_length=160)] | None = None
    expression: str | None = Field(
        default=None,
        min_length=1,
        max_length=4000,
        validation_alias=AliasChoices("expression", "command", "commandTemplate", "command_template"),
    )
    name: str | None = None
    description: str | None = None
    captures: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None
    samples: list[dict[str, Any]] | None = None
    output_schema: dict[str, Any] | None = Field(default=None, alias="outputSchema")
    ttp: Annotated[str, Field(max_length=50000)] | None = None
    enabled: bool | None = None
