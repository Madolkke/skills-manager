from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, Field

from skillhub.models.entities import ContentRef
from skillhub.models.rules.semver import SEMVER_PATTERN

SLUG_PATTERN = r"^[a-z0-9][a-z0-9-]{0,63}$"
TAG_GROUP_ID_PATTERN = r"^[A-Za-z0-9_-]+$"
ENV_TAG_PATTERN = r"^[A-Za-z0-9._-]+$"
IDENTITY_REF_PATTERN = r"^[A-Za-z0-9._@-]{1,120}$"
OPENCODE_AGENT_ID_PATTERN = r"^[A-Za-z0-9_-]+$"

SkillSlug = Annotated[str, Field(min_length=1, max_length=64, pattern=SLUG_PATTERN)]
TagGroupId = Annotated[str, Field(min_length=1, max_length=80, pattern=TAG_GROUP_ID_PATTERN)]
OpencodeAgentId = Annotated[str, Field(min_length=1, max_length=80, pattern=OPENCODE_AGENT_ID_PATTERN)]
TagValue = Annotated[str, Field(min_length=1)]
EnvironmentTagValue = Annotated[str, Field(min_length=1, max_length=64, pattern=ENV_TAG_PATTERN)]
IdentityRef = Annotated[str, Field(min_length=1, max_length=120, pattern=IDENTITY_REF_PATTERN)]
VERSION_CHANGE_SUMMARY_MAX_LENGTH = 1_000
VERSION_DISPLAY_NAME_MAX_LENGTH = 80
VersionChangeSummary = Annotated[str, Field(min_length=1, max_length=VERSION_CHANGE_SUMMARY_MAX_LENGTH)]
VersionDisplayName = Annotated[str, Field(min_length=1, max_length=VERSION_DISPLAY_NAME_MAX_LENGTH)]
SkillVersionSemVer = Annotated[str, Field(min_length=5, max_length=80, pattern=SEMVER_PATTERN)]


class ContentRefPayload(BaseModel):
    kind: str
    locator: str
    digest: str
    path: str | None = None


class SkillTagPayload(BaseModel):
    group_id: TagGroupId
    value: TagValue


def content_ref(payload: ContentRefPayload) -> ContentRef:
    return ContentRef(kind=payload.kind, locator=payload.locator, digest=payload.digest, path=payload.path)  # type: ignore[arg-type]
