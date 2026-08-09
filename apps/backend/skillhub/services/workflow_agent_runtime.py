from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from typing import Any, Literal, cast

from agentscope.agent import Agent, ReActConfig
from agentscope.credential import OpenAICredential
from agentscope.event import EventType
from agentscope.message import Msg, UserMsg
from agentscope.model import OpenAIChatModel
from pydantic import SecretStr

from skillhub.models.errors import ServiceUnavailableError
from skillhub.models.rules.workflow_agent import WorkflowAgentDebugCaseProposal, validate_generated_debug_case_proposal
from skillhub.models.store import SkillHubStore
from skillhub.services.workflow_agent_registry import workflow_agent_descriptor
from skillhub.services.workflow_agent_scope import WorkflowAgentScopeStorage
from skillhub.services.workflow_agent_settings import WorkflowAgentSettings
from skillhub.services.workflow_agent_tools import build_workflow_agent_toolkit

logger = logging.getLogger(__name__)
TERMINAL_RUN_STATUSES = {"completed", "failed", "canceled", "interrupted"}


class WorkflowAgentRuntime:
    def __init__(self, store_factory: Callable[[], SkillHubStore], settings: WorkflowAgentSettings) -> None:
        self.store_factory = store_factory
        self.settings = settings
        self._scope = WorkflowAgentScopeStorage(settings)
        self._scope_lock = asyncio.Lock()
        self._scope_open = False
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._shutting_down = False

    async def startup(self) -> None:
        await asyncio.to_thread(self.store_factory().interrupt_orphaned_workflow_agent_runs)
        if self.settings.available:
            try:
                await self._ensure_scope()
            except Exception as exc:
                logger.warning("workflow agent storage initialization failed error_type=%s", exc.__class__.__name__)

    async def shutdown(self) -> None:
        self._shutting_down = True
        tasks = list(self._tasks.values())
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        await self._scope.close()
        self._scope_open = False

    def schedule(self, run_id: str) -> None:
        if run_id in self._tasks:
            return
        task = asyncio.create_task(self._execute(run_id), name=f"workflow-agent:{run_id}")
        self._tasks[run_id] = task
        task.add_done_callback(lambda _: self._tasks.pop(run_id, None))

    def cancel(self, run_id: str) -> None:
        task = self._tasks.get(run_id)
        if task is not None:
            task.cancel()

    async def delete_scope_sessions(self, *, actor: str, sessions: dict[str, str]) -> None:
        if not sessions or not self.settings.available:
            return
        await self._ensure_scope()
        for agent_id, session_id in sessions.items():
            await self._scope.delete_session(actor=actor, agent_id=agent_id, session_id=session_id)

    async def stream_events(self, *, run_id: str, actor: str, after: int):
        idle_started = time.monotonic()
        while True:
            events = await asyncio.to_thread(
                self.store_factory().list_workflow_agent_events,
                run_id=run_id,
                actor=actor,
                after=after,
            )
            for event in events:
                after = int(event["sequence"])
                idle_started = time.monotonic()
                yield event
            run = await asyncio.to_thread(self.store_factory().workflow_agent_run, run_id=run_id, actor=actor)
            if run["status"] in TERMINAL_RUN_STATUSES and not events:
                return
            if time.monotonic() - idle_started >= 10:
                idle_started = time.monotonic()
                yield None
            await asyncio.sleep(0.2)

    async def _execute(self, run_id: str) -> None:
        response_text = ""
        usage = {"input_tokens": 0, "output_tokens": 0}
        buffered_events: list[dict[str, Any]] = []
        try:
            if not self.settings.available:
                raise ServiceUnavailableError(self.settings.unavailable_reason)
            await self._ensure_scope()
            run = await asyncio.to_thread(self.store_factory().start_workflow_agent_run, run_id=run_id)
            descriptor = workflow_agent_descriptor(str(run["agent_id"]))
            if descriptor is None:
                raise ValueError(f"Unknown Workflow Agent: {run['agent_id']}")
            session = await asyncio.to_thread(
                self.store_factory()._workflow_agent_session_for_runtime,
                session_id=str(run["session_id"]),
            )
            scope_id, state = await self._scope.load_or_create_state(
                actor=str(session["actor_ref"]),
                skill_id=str(run["skill_id"]),
                descriptor=descriptor,
                session_id=dict(session["agentscope_sessions"]).get(descriptor.id),
            )
            if dict(session["agentscope_sessions"]).get(descriptor.id) != scope_id:
                await asyncio.to_thread(
                    self.store_factory().update_workflow_agent_scope_session,
                    session_id=str(run["session_id"]),
                    agent_id=descriptor.id,
                    agentscope_session_id=scope_id,
                )
            agent = self._agent(descriptor, state, run["context_snapshot"]["agent_context"])
            user_message = UserMsg("user", str(run["user_input"]))
            await self._scope.save_message(actor=str(session["actor_ref"]), session_id=scope_id, message=user_message)
            final_message: Msg | None = None
            structured_schema = WorkflowAgentDebugCaseProposal if descriptor.proposal_kind else None
            last_flush = time.monotonic()
            async with asyncio.timeout(self.settings.timeout_seconds):
                async for item in agent.reply_stream(user_message, structured_schema=structured_schema, yield_final_msg=True):
                    if isinstance(item, Msg):
                        final_message = item
                        continue
                    payload = item.model_dump(mode="json")
                    buffered_events.append(payload)
                    response_text += _text_delta(payload)
                    _accumulate_usage(usage, payload)
                    if len(buffered_events) >= 20 or time.monotonic() - last_flush >= 0.1 or str(payload.get("type", "")).endswith("_END"):
                        await self._flush_events(run_id, buffered_events)
                        last_flush = time.monotonic()
                    if await asyncio.to_thread(self.store_factory().workflow_agent_cancel_requested, run_id=run_id):
                        raise asyncio.CancelledError
            await self._flush_events(run_id, buffered_events)
            if final_message is not None:
                await self._scope.save_message(actor=str(session["actor_ref"]), session_id=scope_id, message=final_message)
            await self._scope.save_state(actor=str(session["actor_ref"]), agent_id=descriptor.id, session_id=scope_id, state=agent.state)
            if descriptor.proposal_kind:
                await self._store_proposal(run, final_message)
            await asyncio.to_thread(
                self.store_factory().finish_workflow_agent_run,
                run_id=run_id,
                status="completed",
                response_text=response_text,
                usage=usage,
            )
        except asyncio.CancelledError:
            await self._flush_events(run_id, buffered_events)
            status = "interrupted" if self._shutting_down else "canceled"
            await asyncio.to_thread(self.store_factory().finish_workflow_agent_run, run_id=run_id, status=status, response_text=response_text, usage=usage)
        except TimeoutError:
            await self._flush_events(run_id, buffered_events)
            await asyncio.to_thread(
                self.store_factory().finish_workflow_agent_run,
                run_id=run_id,
                status="failed",
                response_text=response_text,
                usage=usage,
                error={"code": "workflow_agent.timeout", "message": "Workflow Agent 运行超时。"},
            )
        except Exception as exc:
            await self._flush_events(run_id, buffered_events)
            logger.warning("workflow agent run failed run_id=%s error_type=%s", run_id, exc.__class__.__name__)
            await asyncio.to_thread(
                self.store_factory().finish_workflow_agent_run,
                run_id=run_id,
                status="failed",
                response_text=response_text,
                usage=usage,
                error={"code": "workflow_agent.failed", "message": str(exc) or exc.__class__.__name__},
            )

    def _agent(self, descriptor, state, context):
        parameters = OpenAIChatModel.Parameters(
            thinking_enable=True,
            reasoning_effort=cast(Literal["none", "minimal", "low", "medium", "high", "xhigh"] | None, self.settings.reasoning_effort),
        )
        model = OpenAIChatModel(
            credential=OpenAICredential(api_key=SecretStr(self.settings.api_key), base_url=self.settings.base_url),
            model=self.settings.model,
            parameters=parameters,
            stream=True,
            max_retries=0,
            client_kwargs={"timeout": self.settings.timeout_seconds},
        )
        return Agent(
            name=descriptor.id,
            system_prompt=descriptor.system_prompt,
            model=model,
            toolkit=build_workflow_agent_toolkit(context, descriptor.tools),
            state=state,
            react_config=ReActConfig(max_iters=1_000_000),
        )

    async def _store_proposal(self, run: dict[str, Any], message: Msg | None) -> None:
        if message is None or message.structured_output is None:
            raise ValueError("Workflow Agent did not return a structured proposal.")
        proposal = WorkflowAgentDebugCaseProposal.model_validate(message.structured_output)
        source = await asyncio.to_thread(self.store_factory().workflow_agent_document_source, skill_id=str(run["skill_id"]))
        document = source["document"]
        selected_step_id = str(run["selection"].get("id") or "")
        validate_generated_debug_case_proposal(document, proposal, selected_step_id=selected_step_id)
        await asyncio.to_thread(
            self.store_factory().insert_workflow_agent_proposal,
            values={
                "run_id": run["id"],
                "skill_id": run["skill_id"],
                "kind": "debug_case_draft",
                "status": "proposed",
                "payload": proposal.model_dump(mode="json"),
                "base_revision": run["base_revision"],
                "base_workflow_digest": run["base_workflow_digest"],
                "draft_digest": run["draft_digest"],
                "applied_result": {},
                "created_by": run["created_by"],
            },
        )

    async def _flush_events(self, run_id: str, events: list[dict[str, Any]]) -> None:
        if not events:
            return
        batch = list(events)
        events.clear()
        await asyncio.to_thread(self.store_factory().append_workflow_agent_events, run_id=run_id, payloads=batch)

    async def _ensure_scope(self) -> None:
        if self._scope_open:
            return
        async with self._scope_lock:
            if not self._scope_open:
                await self._scope.open()
                self._scope_open = True


def _text_delta(payload: dict[str, Any]) -> str:
    return str(payload.get("delta") or "") if payload.get("type") == EventType.TEXT_BLOCK_DELTA.value else ""


def _accumulate_usage(usage: dict[str, int], payload: dict[str, Any]) -> None:
    if payload.get("type") != EventType.MODEL_CALL_END.value:
        return
    usage["input_tokens"] += int(payload.get("input_tokens") or 0)
    usage["output_tokens"] += int(payload.get("output_tokens") or 0)


__all__ = ["TERMINAL_RUN_STATUSES", "WorkflowAgentRuntime"]
