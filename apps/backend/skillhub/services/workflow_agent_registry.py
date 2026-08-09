from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WorkflowAgentDescriptor:
    id: str
    name: str
    description: str
    prompt_version: str
    system_prompt: str
    tools: tuple[str, ...]
    proposal_kind: str | None = None

    def public_payload(self) -> dict[str, object]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "prompt_version": self.prompt_version,
            "tools": list(self.tools),
            "proposal_kind": self.proposal_kind,
        }


WORKFLOW_AGENTS = {
    "workflow_assistant": WorkflowAgentDescriptor(
        id="workflow_assistant",
        name="Workflow 助手",
        description="解释当前 Workflow、定位校验问题并提供写作建议。",
        prompt_version="1.0.0",
        system_prompt=(
            "你是 SkillHub Workflow 写作助手。只根据领域工具返回的当前 Workflow 上下文回答。"
            "可以解释结构、校验问题、表达式和采集定义，但不得声称已经保存或执行任何修改。"
            "collectionSnapshots 只包含当前选择相关的定义；必须结合节点摘要中的 collectionCalls 判断全局是否存在采集，"
            "不得把未加载的定义误判为 Workflow 不存在采集。"
            "引用节点、参数和采集时必须使用上下文中的真实名称和 ID；信息不足时明确指出。"
        ),
        tools=("read_workflow_context", "read_workflow_validation", "read_existing_debug_cases"),
    ),
    "debug_case_generator": WorkflowAgentDescriptor(
        id="debug_case_generator",
        name="测试用例生成",
        description="为当前 Step 的每个直接目标生成可确认的单步调试例候选。",
        prompt_version="1.0.0",
        system_prompt=(
            "你是 SkillHub Workflow 单步调试例生成 Agent。必须先读取 Workflow 上下文和已有调试例。"
            "为当前选中 Step 的每个直接拓扑目标至少生成一个候选，总数不得超过 10。"
            "workflow_inputs 必须使用 input ID，collection_fixtures 必须使用 call ID，outputs 必须使用 output ID。"
            "允许依据相关 Collection 的原始样例生成 raw_output，但不得启动运行或直接保存案例。"
        ),
        tools=("read_workflow_context", "read_workflow_validation", "read_existing_debug_cases"),
        proposal_kind="debug_case_draft",
    ),
}


def workflow_agent_descriptor(agent_id: str) -> WorkflowAgentDescriptor | None:
    return WORKFLOW_AGENTS.get(agent_id)


def workflow_agent_catalog() -> list[dict[str, object]]:
    return [descriptor.public_payload() for descriptor in WORKFLOW_AGENTS.values()]


__all__ = ["WorkflowAgentDescriptor", "workflow_agent_catalog", "workflow_agent_descriptor"]
