from __future__ import annotations

from importlib.metadata import version

from agentscope.event import EventType, ThinkingBlockDeltaEvent, ToolCallStartEvent, ToolResultEndEvent
from agentscope.message import ToolResultState

from skillhub.services.workflow_agent_scope import _agentscope_database_url
from skillhub.services.workflow_agent_settings import WorkflowAgentSettings


def test_agentscope_version_and_native_event_contract_are_pinned() -> None:
    assert version("agentscope") == "2.0.6"
    assert [item.value for item in EventType] == [
        "REPLY_START", "REPLY_END", "MODEL_CALL_START", "MODEL_CALL_END",
        "TEXT_BLOCK_START", "TEXT_BLOCK_DELTA", "TEXT_BLOCK_END",
        "DATA_BLOCK_START", "DATA_BLOCK_DELTA", "DATA_BLOCK_END",
        "THINKING_BLOCK_START", "THINKING_BLOCK_DELTA", "THINKING_BLOCK_END", "HINT_BLOCK",
        "TOOL_CALL_START", "TOOL_CALL_DELTA", "TOOL_CALL_END",
        "TOOL_RESULT_START", "TOOL_RESULT_TEXT_DELTA", "TOOL_RESULT_DATA_DELTA", "TOOL_RESULT_END",
        "EXCEED_MAX_ITERS", "REQUIRE_USER_CONFIRM", "REQUIRE_EXTERNAL_EXECUTION",
        "USER_CONFIRM_RESULT", "USER_INTERRUPT", "EXTERNAL_EXECUTION_RESULT", "CUSTOM",
    ]
    events = [
        ThinkingBlockDeltaEvent(id="thinking-1", reply_id="reply-1", block_id="block-1", delta="reason"),
        ToolCallStartEvent(id="tool-1", reply_id="reply-1", tool_call_id="call-1", tool_call_name="read_workflow_context"),
        ToolResultEndEvent(id="result-1", reply_id="reply-1", tool_call_id="call-1", state=ToolResultState.SUCCESS),
    ]
    assert [event.model_dump(mode="json")["type"] for event in events] == [
        "THINKING_BLOCK_DELTA", "TOOL_CALL_START", "TOOL_RESULT_END",
    ]
    assert events[0].model_dump(mode="json")["delta"] == "reason"


def test_agent_settings_require_fixed_provider_configuration() -> None:
    missing = WorkflowAgentSettings.from_environment({}, database_url="postgresql+psycopg://localhost/skillhub")
    assert missing.available is False
    assert missing.unavailable_reason

    configured = WorkflowAgentSettings.from_environment(
        {
            "WORKFLOW_AGENT_MODEL_BASE_URL": "https://provider.example/v1/",
            "WORKFLOW_AGENT_MODEL_API_KEY": "secret",
            "WORKFLOW_AGENT_MODEL": "model-1",
            "WORKFLOW_AGENT_TIMEOUT_SECONDS": "42",
            "WORKFLOW_AGENT_REASONING_EFFORT": "high",
        },
        database_url="postgresql+psycopg://localhost/skillhub",
    )
    assert configured.available is True
    assert configured.base_url == "https://provider.example/v1"
    assert configured.timeout_seconds == 42
    assert configured.reasoning_effort == "high"


def test_agent_settings_fall_back_to_existing_deepseek_configuration() -> None:
    settings = WorkflowAgentSettings.from_environment(
        {
            "DEEPSEEK_BASE_URL": "https://provider.example/v1",
            "DEEPSEEK_API_KEY": "secret",
            "OPENCODE_DEFAULT_MODEL": "deepseek/example-model",
        },
        database_url="postgresql+psycopg://localhost/skillhub",
    )

    assert settings.available is True
    assert settings.base_url == "https://provider.example/v1"
    assert settings.model == "example-model"


def test_agentscope_uses_an_isolated_postgresql_schema() -> None:
    url = _agentscope_database_url("postgresql+psycopg://user:pass@localhost/skillhub")
    assert url.startswith("postgresql+asyncpg://")
