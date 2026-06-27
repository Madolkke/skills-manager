from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from skillhub.models.errors import InvariantError


@dataclass(frozen=True)
class AssertionParam:
    name: str
    label: str
    type: str
    required: bool = True
    default: Any = None
    placeholder: str = ""
    help: str = ""
    min: float | None = None
    max: float | None = None


@dataclass(frozen=True)
class AssertionResult:
    passed: bool
    actual: str
    reason: str
    details: dict[str, Any]


@dataclass(frozen=True)
class AssertionContext:
    agent_output: str
    workdir: Path
    before_snapshot: set[str]
    after_snapshot: set[str]
    step: dict[str, Any]
    run_metadata: dict[str, Any]
    reasoning_text: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)


class AssertionTemplate:
    """Base class for eval step assertion templates."""

    id = ""
    name = ""
    description = ""
    category = "通用"
    params: tuple[AssertionParam, ...] = ()

    def definition(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "params_schema": [param.__dict__ for param in self.params],
        }

    def normalize_params(self, params: dict[str, Any] | None) -> dict[str, Any]:
        raw = dict(params or {})
        clean: dict[str, Any] = {}
        for param in self.params:
            value = raw.get(param.name, param.default)
            if param.required and _blank(value):
                raise InvariantError(f"Assertion parameter is required: {param.name}")
            clean[param.name] = value
        return clean

    def evaluate(self, context: AssertionContext, params: dict[str, Any]) -> AssertionResult:
        raise NotImplementedError


def _blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())
