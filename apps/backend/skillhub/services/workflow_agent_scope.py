from __future__ import annotations

from typing import TYPE_CHECKING

from agentscope.agent import ContextConfig, ReActConfig
from agentscope.app.storage import AgentData, AgentRecord, SessionConfig
from agentscope.app.storage._sql._storage import AsyncSQLAlchemyStorage
from agentscope.message import Msg
from agentscope.state import AgentState
from sqlalchemy.engine import make_url

from skillhub.services.workflow_agent_registry import WorkflowAgentDescriptor

if TYPE_CHECKING:
    from skillhub.services.workflow_agent_settings import WorkflowAgentSettings


class WorkflowAgentScopeStorage:
    def __init__(self, settings: "WorkflowAgentSettings") -> None:
        self._settings = settings
        self._storage: AsyncSQLAlchemyStorage | None = None

    async def open(self) -> None:
        if self._storage is not None:
            return
        storage = AsyncSQLAlchemyStorage(
            _agentscope_database_url(self._settings.database_url),
            create_tables=True,
            engine_kwargs={"connect_args": {"server_settings": {"search_path": "workflow_agent_scope"}}},
        )
        await storage.__aenter__()
        self._storage = storage

    async def close(self) -> None:
        if self._storage is not None:
            await self._storage.aclose()
            self._storage = None

    async def load_or_create_state(
        self,
        *,
        actor: str,
        skill_id: str,
        descriptor: WorkflowAgentDescriptor,
        session_id: str | None,
    ) -> tuple[str, AgentState]:
        storage = self._require_storage()
        if await storage.get_agent(actor, descriptor.id) is None:
            await storage.upsert_agent(
                actor,
                AgentRecord(
                    id=descriptor.id,
                    user_id=actor,
                    data=AgentData(
                        name=descriptor.name,
                        system_prompt=descriptor.system_prompt,
                        context_config=ContextConfig(),
                        react_config=ReActConfig(max_iters=1_000_000),
                    ),
                ),
            )
        record = await storage.get_session(actor, descriptor.id, session_id) if session_id else None
        if record is None:
            record = await storage.upsert_session(
                actor,
                descriptor.id,
                SessionConfig(workspace_id=f"skillhub-workflow:{skill_id}", name=descriptor.name),
                session_id=session_id,
            )
        return record.id, record.state

    async def save_state(self, *, actor: str, agent_id: str, session_id: str, state: AgentState) -> None:
        await self._require_storage().update_session_state(actor, agent_id, session_id, state)

    async def save_message(self, *, actor: str, session_id: str, message: Msg) -> None:
        await self._require_storage().upsert_message(actor, session_id, message)

    async def delete_session(self, *, actor: str, agent_id: str, session_id: str) -> None:
        await self._require_storage().delete_session(actor, agent_id, session_id)

    def _require_storage(self) -> AsyncSQLAlchemyStorage:
        if self._storage is None:
            raise RuntimeError("AgentScope storage is not open")
        return self._storage


def _agentscope_database_url(raw: str) -> str:
    url = make_url(raw)
    url = url.set(drivername="postgresql+asyncpg")
    return url.render_as_string(hide_password=False)


__all__ = ["WorkflowAgentScopeStorage"]
