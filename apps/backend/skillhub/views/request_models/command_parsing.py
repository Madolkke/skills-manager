"""系统命令回显解析接口的严格请求与响应契约。"""
from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator


class CommandParsePayload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    input: str = Field(min_length=1, max_length=4000, description="不含设备提示符的单条具体命令")
    echo: str = Field(description="原始回显，UTF-8 上限 1 MiB")

    @field_validator("input")
    @classmethod
    def single_command(cls, value: str) -> str:
        """去首尾空白，拒绝空命令与多行输入。"""
        value = value.strip()
        if not value or "\n" in value or "\r" in value or "\x00" in value:
            raise ValueError("input 必须为非空单行命令。")
        return value


class ParsedCommand(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: str
    key: str
    name: str
    expression: str


class ParseWarning(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    code: str
    path: str = Field(description="JSON Pointer，空字符串表示根节点")
    message: str


class ParseValidation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    valid: bool
    warnings: list[ParseWarning]


class CommandParseResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    command: ParsedCommand
    result: JsonValue
    validation: ParseValidation


class CommandParseErrorResponse(BaseModel):
    detail: str
    code: str
    candidates: list[ParsedCommand] = Field(default_factory=list)
    field_errors: list[dict[str, str]] = Field(default_factory=list)
