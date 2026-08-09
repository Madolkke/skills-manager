from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class WorkflowAgentSettings:
    database_url: str
    base_url: str
    api_key: str
    model: str
    timeout_seconds: float = 300.0
    reasoning_effort: str | None = None

    @classmethod
    def from_environment(cls, environment: Mapping[str, str], *, database_url: str) -> "WorkflowAgentSettings":
        timeout = _positive_float(environment.get("WORKFLOW_AGENT_TIMEOUT_SECONDS"), default=300.0)
        effort = (environment.get("WORKFLOW_AGENT_REASONING_EFFORT") or "").strip() or None
        if effort not in {None, "none", "minimal", "low", "medium", "high", "xhigh"}:
            effort = None
        return cls(
            database_url=database_url,
            base_url=_configured_value(environment, "WORKFLOW_AGENT_MODEL_BASE_URL", "DEEPSEEK_BASE_URL").rstrip("/"),
            api_key=_configured_value(environment, "WORKFLOW_AGENT_MODEL_API_KEY", "DEEPSEEK_API_KEY"),
            model=_configured_model(environment),
            timeout_seconds=timeout,
            reasoning_effort=effort,
        )

    @property
    def available(self) -> bool:
        return bool(self.base_url and self.api_key and self.model and self.database_url.startswith("postgresql"))

    @property
    def unavailable_reason(self) -> str:
        if not self.base_url or not self.api_key or not self.model:
            return "Workflow Agent 模型尚未配置。"
        if not self.database_url.startswith("postgresql"):
            return "Workflow Agent 需要 PostgreSQL 持久化。"
        return ""


def _positive_float(raw: str | None, *, default: float) -> float:
    try:
        value = float(raw) if raw else default
    except ValueError:
        return default
    return value if value > 0 else default


def _configured_value(environment: Mapping[str, str], primary: str, fallback: str) -> str:
    return (environment.get(primary) or environment.get(fallback) or "").strip()


def _configured_model(environment: Mapping[str, str]) -> str:
    explicit = (environment.get("WORKFLOW_AGENT_MODEL") or "").strip()
    if explicit:
        return explicit
    opencode_model = (environment.get("OPENCODE_DEFAULT_MODEL") or "").strip()
    return opencode_model.split("/", 1)[-1]


__all__ = ["WorkflowAgentSettings"]
