from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from skillhub.views.request_models.common import SkillTagPayload, SkillVersionSemVer

SKILL_BUILDER_MESSAGE_MAX_LENGTH = 20_000
SKILL_BUILDER_FILE_CONTENT_MAX_LENGTH = 200_000
SkillBuilderMessageText = Annotated[str, Field(min_length=1, max_length=SKILL_BUILDER_MESSAGE_MAX_LENGTH)]
SkillBuilderFileContent = Annotated[str, Field(max_length=SKILL_BUILDER_FILE_CONTENT_MAX_LENGTH)]


class CreateSkillBuilderSessionPayload(BaseModel):
    title: Annotated[str, Field(max_length=160)] | None = None
    replace_running: bool = False


class SkillBuilderMessagePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: SkillBuilderMessageText
    intent: str = "chat"
    provider_id: Annotated[str, Field(max_length=120)] | None = None
    model_id: Annotated[str, Field(max_length=120)] | None = None


class SkillBuilderDraftFilePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: Annotated[str, Field(min_length=1, max_length=240)]
    content_text: SkillBuilderFileContent


class UpdateSkillBuilderDraftPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    files: list[SkillBuilderDraftFilePayload] = Field(min_length=1, max_length=100)


class UpdateSkillBuilderWorkspacePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    files: list[SkillBuilderDraftFilePayload] = Field(default_factory=list, max_length=100)


class CreateSkillFromBuilderPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: SkillVersionSemVer
    tags: list[SkillTagPayload] = Field(default_factory=list)
    files: list[SkillBuilderDraftFilePayload] | None = Field(default=None, max_length=100)
