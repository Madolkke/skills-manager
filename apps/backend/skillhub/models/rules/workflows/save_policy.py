"""工作流预检与正式保存共用的诊断阻断规则。"""

from typing import Any

from skillhub.models.errors import InvariantError


def blocking_workflow_errors(
    validation: dict[str, Any], *, validation_policy: str,
    invalid_policy_message: str | None = None,
) -> list[dict[str, Any]]:
    """统一检查保存策略并选出阻断错误，保留调用入口的既有错误措辞。"""
    if validation_policy not in {"draft", "strict"}:
        raise InvariantError(invalid_policy_message or f"Unsupported validation policy: {validation_policy}")
    errors = validation["errors"]
    if validation_policy == "strict":
        return errors
    return [
        item for item in errors if item["code"].startswith("FUNCTION_")
        or item["code"] in {"UNREGISTERED_CALL", "INCOMPATIBLE_BINDING_SCHEMA"}
    ]
