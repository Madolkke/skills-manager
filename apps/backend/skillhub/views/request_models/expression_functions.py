"""函数库管理接口响应模型。"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from .admin import AdminExpressionFunctionPayload


class ExpressionFunctionResponse(AdminExpressionFunctionPayload):
    id: str
    createdAt: datetime
    updatedAt: datetime
    createdBy: str
    updatedBy: str


class ExpressionFunctionDeleted(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    deleted: bool
