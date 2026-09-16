"""MCP 查询参数和字段定位；编辑操作模型由 workflow_authoring 提供。"""

from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

from skillhub.views.request_models.common import SkillTagPayload
from skillhub.views.request_models.workflows import WorkflowDescription

Offset = Annotated[int, Field(ge=0)]
Limit = Annotated[int, Field(ge=1, le=100)]
Identifier = Annotated[str, Field(min_length=1)]
Revision = Annotated[int, Field(ge=1)]
ValidationPolicy = Literal["draft", "strict"]
WorkflowView = Literal["outline", "full", "node"]
ContractTopic = Literal["overview", "changes", "collections", "expressions", "logs"]
CreateDescription = Annotated[WorkflowDescription, Field(min_length=1)]
WorkflowName = Annotated[
    str,
    BeforeValidator(lambda value: value.strip() if isinstance(value, str) else value),
    Field(min_length=1, max_length=160),
]


class AuthoringSkillTag(SkillTagPayload):
    """复用现有标签字段，并要求 MCP 输入不得携带额外字段。"""

    model_config = ConfigDict(extra="forbid", strict=True)


class ExpressionSelection(BaseModel):
    """定位需要检查作用域的 Workflow 作者字段。"""

    model_config = ConfigDict(extra="forbid", strict=True)

    node_id: Identifier
    field: Literal["conditionExpression", "conditionText", "rootCause", "repairRecommendation", "binding"]
    call_id: Identifier | None = None
    input_id: Identifier | None = None
    transition_id: Identifier | None = None
