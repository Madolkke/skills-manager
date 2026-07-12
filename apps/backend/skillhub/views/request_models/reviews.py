from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field

from skillhub.views.request_models.common import IdentityRef


class ReviewPublishTargetPayload(BaseModel):
    publish_target_id: str
    auto_submit_on_pass: bool = True


class ReviewSubjectPayload(BaseModel):
    subject_type: Literal["user", "group"] = "user"
    subject_id: IdentityRef


class CreateReviewRequestPayload(BaseModel):
    skill_version_id: str
    publish_targets: list[ReviewPublishTargetPayload] = Field(default_factory=list)
    reviewer_sources: list[ReviewSubjectPayload] = Field(default_factory=list)


class SubmitReviewResponsePayload(BaseModel):
    score: int = Field(ge=-1, le=1)
    comment: Annotated[str, Field(max_length=4000)] = ""


class NotificationUpdatePayload(BaseModel):
    read: bool = True


class CreatePublishRecordPayload(BaseModel):
    skill_version_id: str
    review_request_id: str
    publish_target_id: str
