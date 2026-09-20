"""独立分页接口契约；既有列表接口不改变结构。"""
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from .pagination_items import ReviewSummary, SkillListItem

Item = TypeVar("Item")


class PageQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)


class TagFilter(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    group_id: str
    value: str


class SkillPageQuery(PageQuery):
    model_config = ConfigDict(extra="forbid", strict=True)
    query: str = Field("", max_length=4000)
    category: Literal["all", "workflow", "verified", "untested", "mine"] = "all"
    sort: Literal["updated", "score", "name"] = "updated"
    tags: list[TagFilter] = Field(default_factory=list)
    evaluations_visible: bool = True
    diagnostic_group: str | None = None
    diagnostic_kind: Literal["orphaned", "missing_required"] | None = None


class PageResponse(BaseModel, Generic[Item]):
    model_config = ConfigDict(extra="forbid")
    items: list[Item]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)


class SkillPageResponse(PageResponse[SkillListItem]):
    counts: dict[str, int] = Field(default_factory=dict)
    tag_counts: dict[str, int] = Field(default_factory=dict)


class ReviewPageResponse(PageResponse[ReviewSummary]):
    counts: dict[str, int]


class VersionPageQuery(PageQuery):
    query: str = Field("", max_length=4000)


class RolePageQuery(PageQuery):
    subject: str = ""
    resource: str = ""
    resource_type: Literal["", "skill", "skill_tag", "global"] = ""
    role: Literal["", "viewer", "evaluator", "reviewer", "maintainer", "owner", "admin"] = ""


class ReviewPageQuery(PageQuery):
    status: Literal["", "open", "closed", "cancelled"] = ""


class RunPageQuery(PageQuery):
    eval_set_id: str | None = None
    skill_version_id: str | None = None
    status: str | None = None
