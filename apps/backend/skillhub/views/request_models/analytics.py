"""运营访问接口的严格 HTTP 模型。"""

from uuid import UUID

from pydantic import BaseModel, ConfigDict


class SkillVisitPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: UUID


class SkillVisitResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    ok: bool = True
