from __future__ import annotations

from typing import Any

from skillhub.models.errors import ConflictError, FieldError, FieldInvariantError, InvariantError, ServiceUnavailableError
from skillhub.models.rules.workflow_agent_context import build_workflow_agent_context, workflow_agent_draft_digest
from skillhub.models.rules.workflows import normalize_workflow_document
from skillhub.models.rules.workflows.schema import BaseStep, WorkflowBundle
from skillhub.models.store import SkillHubStore
from skillhub.services.base import ServiceBase
from skillhub.services.workflow_agent_registry import workflow_agent_catalog, workflow_agent_descriptor
from skillhub.services.workflow_agent_runtime import WorkflowAgentRuntime


class WorkflowAgentService(ServiceBase[SkillHubStore]):
    def __init__(self, store: SkillHubStore, runtime: WorkflowAgentRuntime) -> None:
        super().__init__(store)
        self.runtime = runtime

    def catalog(self, *, skill_id: str, actor: str) -> dict[str, object]:
        self.store.require_workflow_agent_access(skill_id=skill_id, actor=actor)
        return {
            "agents": workflow_agent_catalog(),
            "available": self.runtime.settings.available,
            "unavailable_reason": self.runtime.settings.unavailable_reason,
            "agentscope_version": "2.0.6",
        }

    def list_sessions(self, *, skill_id: str, actor: str) -> list[dict[str, object]]:
        return [_public_session(item) for item in self.store.list_workflow_agent_sessions(skill_id=skill_id, actor=actor)]

    def create_session(self, *, skill_id: str, actor: str, title: str) -> dict[str, object]:
        clean_title = title.strip()[:160]
        return _public_session(self.store.create_workflow_agent_session(skill_id=skill_id, actor=actor, title=clean_title))

    def archive_session(self, *, session_id: str, actor: str) -> dict[str, object]:
        return _public_session(self.store.archive_workflow_agent_session(session_id=session_id, actor=actor))

    async def delete_session(self, *, session_id: str, actor: str) -> dict[str, bool]:
        result = self.store.delete_workflow_agent_session(session_id=session_id, actor=actor)
        await self.runtime.delete_scope_sessions(actor=str(result["actor_ref"]), sessions=dict(result["agentscope_sessions"]))
        return {"deleted": True}

    def create_run(
        self,
        *,
        session_id: str,
        agent_id: str,
        content: str,
        base_revision: int,
        draft: dict[str, Any],
        selection: dict[str, Any],
        actor: str,
    ) -> dict[str, object]:
        descriptor = workflow_agent_descriptor(agent_id)
        if descriptor is None:
            raise FieldInvariantError(
                "Workflow Agent 不存在。",
                [FieldError(field="agent_id", message="请选择可用的 Workflow Agent。", code="workflow_agent.unknown_agent")],
            )
        if not self.runtime.settings.available:
            raise ServiceUnavailableError(self.runtime.settings.unavailable_reason)
        clean_content = content.strip()
        if not clean_content:
            raise InvariantError("Workflow Agent input cannot be empty.")
        source = self.store.workflow_agent_run_source(session_id=session_id, actor=actor)
        if source["session"]["status"] != "active":
            raise ConflictError("The Workflow Agent session is archived.")
        if int(source["workflow_revision"]) != base_revision:
            raise ConflictError("Workflow revision changed. Reload before starting the Agent.")
        normalized = normalize_workflow_document(draft)
        if normalized["workflow"]["id"] != source["workflow_id"]:
            raise FieldInvariantError(
                "Workflow 草稿不属于当前 Skill。",
                [FieldError(field="draft.workflow.id", message="Workflow 草稿身份不一致。", code="workflow_agent.workflow_mismatch")],
            )
        step_id = _selected_step_id(normalized, selection) if descriptor.proposal_kind else _optional_selected_step_id(normalized, selection)
        existing_cases = (
            self.store.list_workflow_debug_cases(skill_id=source["session"]["skill_id"], actor=actor, step_id=step_id)
            if step_id is not None
            else []
        )
        agent_context = build_workflow_agent_context(
            normalized,
            selection=selection,
            existing_cases=existing_cases,
            recent_history=source["recent_history"],
        )
        draft_digest = workflow_agent_draft_digest(normalized)
        row = self.store.insert_workflow_agent_run(
            values={
                "session_id": session_id,
                "skill_id": source["session"]["skill_id"],
                "agent_id": agent_id,
                "status": "starting",
                "user_input": clean_content,
                "response_text": "",
                "selection": selection,
                "context_snapshot": {"selection": selection, "agent_context": agent_context},
                "base_revision": base_revision,
                "base_workflow_digest": source["workflow_digest"],
                "draft_digest": draft_digest,
                "cancel_requested": False,
                "usage": {},
                "error": None,
                "created_by": actor,
                "started_at": None,
                "finished_at": None,
            }
        )
        return _public_run(row, proposal=None)

    def get_run(self, *, run_id: str, actor: str) -> dict[str, object]:
        run = self.store.workflow_agent_run(run_id=run_id, actor=actor)
        proposal = self.store.workflow_agent_proposal_for_run(run_id=run_id, actor=actor)
        return _public_run(run, proposal=proposal)

    def list_runs(self, *, session_id: str, actor: str) -> list[dict[str, object]]:
        return [
            _public_run(run, proposal=self.store.workflow_agent_proposal_for_run(run_id=run["id"], actor=actor))
            for run in self.store.list_workflow_agent_runs(session_id=session_id, actor=actor)
        ]

    def cancel_run(self, *, run_id: str, actor: str) -> dict[str, object]:
        run = self.store.request_workflow_agent_cancel(run_id=run_id, actor=actor)
        self.runtime.cancel(run_id)
        return _public_run(run, proposal=self.store.workflow_agent_proposal_for_run(run_id=run_id, actor=actor))

    async def schedule_run(self, run_id: str) -> None:
        self.runtime.schedule(run_id)

    def event_stream(self, *, run_id: str, actor: str, after: int):
        return self.runtime.stream_events(run_id=run_id, actor=actor, after=after)

    def apply_proposal(self, *, proposal_id: str, candidates: list[dict[str, Any]], actor: str) -> dict[str, object]:
        result = self.store.apply_workflow_agent_proposal(proposal_id=proposal_id, cases=candidates, actor=actor)
        if result["stale"]:
            raise ConflictError("Workflow Agent proposal is stale. Save the matching Workflow draft and generate again.")
        return result


def _selected_step_id(document: dict[str, Any], selection: dict[str, Any]) -> str:
    step_id = _optional_selected_step_id(document, selection)
    if step_id is None:
        raise FieldInvariantError(
            "测试用例生成需要带直接目标的 Step。",
            [FieldError(field="selection.id", message="请选择至少包含一个直接目标的 Step。", code="workflow_agent.step_required")],
        )
    bundle = WorkflowBundle.model_validate(document)
    step = next((node for node in bundle.workflow.nodes if isinstance(node, BaseStep) and node.id == step_id), None)
    if step is None or not step.topology:
        raise FieldInvariantError(
            "测试用例生成需要带直接目标的 Step。",
            [FieldError(field="selection.id", message="请选择至少包含一个直接目标的 Step。", code="workflow_agent.step_required")],
        )
    return step_id


def _optional_selected_step_id(document: dict[str, Any], selection: dict[str, Any]) -> str | None:
    if selection.get("type") != "step" or not selection.get("id"):
        return None
    step_id = str(selection["id"])
    return step_id if any(node.get("id") == step_id and "stepType" in node for node in document["workflow"]["nodes"]) else None


def _public_session(row: dict[str, Any]) -> dict[str, object]:
    return {key: value for key, value in row.items() if key != "agentscope_sessions"}


def _public_run(row: dict[str, Any], *, proposal: dict[str, Any] | None) -> dict[str, object]:
    payload = {key: value for key, value in row.items() if key != "context_snapshot"}
    payload["proposal"] = _public_proposal(proposal) if proposal else None
    return payload


def _public_proposal(row: dict[str, Any]) -> dict[str, object]:
    return dict(row)


__all__ = ["WorkflowAgentService"]
