from dataclasses import dataclass


class DomainError(Exception):
    """Base class for domain invariant failures."""


class CommandParseError(DomainError):
    """回显解析失败，保留稳定错误码和可公开候选。"""

    def __init__(self, code: str, detail: str, status: int, candidates: list[dict[str, str]] | None = None):
        """保存协议适配需要的信息，不携带模板、回显或底层异常文本。"""
        super().__init__(detail)
        self.code = code
        self.status = status
        self.candidates = candidates or []


class NotFoundError(DomainError):
    """Raised when a referenced domain object does not exist."""


class InvariantError(DomainError):
    """Raised when a command would violate a domain rule."""


class WorkflowValidationError(InvariantError):
    """工作流写入校验失败，并携带可定位的完整诊断。"""

    def __init__(self, detail: str, validation: dict):
        """保留领域诊断供各协议适配层返回。"""
        super().__init__(detail)
        self.validation = validation


class ConflictError(DomainError):
    """Raised when a command conflicts with the current resource state."""


class ServiceUnavailableError(DomainError):
    """Raised when a required external service is not configured or unavailable."""


@dataclass(frozen=True)
class FieldError:
    """Machine-readable field error for API clients."""

    field: str
    message: str
    code: str

    def to_payload(self) -> dict[str, str]:
        return {"field": self.field, "message": self.message, "code": self.code}


class FieldInvariantError(InvariantError):
    """Raised when a domain rule can be mapped to one or more fields."""

    def __init__(self, detail: str, field_errors: list[FieldError]):
        super().__init__(detail)
        self.field_errors = field_errors


class PermissionDeniedError(DomainError):
    """Raised when an actor lacks permission for a protected action."""
