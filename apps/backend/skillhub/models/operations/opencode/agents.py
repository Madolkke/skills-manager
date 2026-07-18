from __future__ import annotations

from typing import Any

from sqlalchemy import insert, update

from skillhub.models.entities import new_id, utc_now
from skillhub.models.errors import InvariantError, NotFoundError
from skillhub.models.rules.opencode_agents import (
    normalize_agent_description,
    normalize_agent_id,
    normalize_agent_name,
    normalize_agent_optional_text,
    normalize_agent_permission,
    normalize_agent_prompt,
    normalize_agent_steps,
    normalize_agent_temperature,
)
from skillhub.models.schema import orm


class OpencodeAgentMixin:
    def list_opencode_agents_admin(self, *, include_deleted: bool = False) -> list[dict[str, Any]]:
        with self._read_session() as connection:
            query = orm.select_entity(orm.OpencodeAgent).order_by(orm.OpencodeAgent.name, orm.OpencodeAgent.id)
            if not include_deleted:
                query = query.where(orm.OpencodeAgent.deleted_at.is_(None))
            rows = connection.execute(query).mappings().all()
            return [self._opencode_agent_dict(row) for row in rows]

    def list_enabled_opencode_agents(self) -> list[dict[str, Any]]:
        with self._read_session() as connection:
            rows = (
                connection.execute(
                    orm.select_entity(orm.OpencodeAgent)
                    .where(orm.OpencodeAgent.enabled.is_(True))
                    .where(orm.OpencodeAgent.deleted_at.is_(None))
                    .order_by(orm.OpencodeAgent.name, orm.OpencodeAgent.id)
                )
                .mappings()
                .all()
            )
            return [self._opencode_agent_dict(row) for row in rows]

    def create_opencode_agent(self, *, payload: dict[str, Any], actor: str) -> dict[str, Any]:
        created_at = utc_now()
        row = self._clean_opencode_agent_payload(payload, actor=actor, created_at=created_at, require_id=True)
        agent_id = row["id"]
        with self._write_session() as connection:
            existing = connection.execute(orm.select_entity(orm.OpencodeAgent).where(orm.OpencodeAgent.id == agent_id)).mappings().one_or_none()
            if existing is not None and existing["deleted_at"] is None:
                raise InvariantError(f"Opencode Agent already exists: {agent_id}")
            if existing is not None:
                connection.execute(
                    update(orm.OpencodeAgent)
                    .where(orm.OpencodeAgent.id == agent_id)
                    .values(**row, deleted_at=None)
                )
            else:
                connection.execute(insert(orm.OpencodeAgent).values(**row))
            self._audit_opencode_agent(connection, action="opencode_agent.created", agent_id=agent_id, actor=actor, payload={"name": row["name"]})
        return self.opencode_agent_detail(agent_id=agent_id, include_deleted=False)

    def update_opencode_agent(self, *, agent_id: str, payload: dict[str, Any], actor: str) -> dict[str, Any]:
        clean_id = normalize_agent_id(agent_id)
        updated_at = utc_now()
        values = self._clean_opencode_agent_payload(payload, actor=actor, created_at=updated_at, require_id=False)
        values.pop("id", None)
        values.pop("created_at", None)
        values.pop("created_by", None)
        values["updated_at"] = updated_at
        values["updated_by"] = actor
        with self._write_session() as connection:
            self._opencode_agent_row(connection, clean_id, include_deleted=False)
            connection.execute(update(orm.OpencodeAgent).where(orm.OpencodeAgent.id == clean_id).values(**values))
            self._audit_opencode_agent(connection, action="opencode_agent.updated", agent_id=clean_id, actor=actor, payload={"name": values["name"]})
        return self.opencode_agent_detail(agent_id=clean_id, include_deleted=False)

    def delete_opencode_agent(self, *, agent_id: str, actor: str) -> dict[str, bool]:
        clean_id = normalize_agent_id(agent_id)
        deleted_at = utc_now()
        with self._write_session() as connection:
            row = self._opencode_agent_row(connection, clean_id, include_deleted=False)
            connection.execute(
                update(orm.OpencodeAgent)
                .where(orm.OpencodeAgent.id == clean_id)
                .values(enabled=False, deleted_at=deleted_at, updated_at=deleted_at, updated_by=actor)
            )
            self._audit_opencode_agent(connection, action="opencode_agent.deleted", agent_id=clean_id, actor=actor, payload={"name": row["name"]})
        return {"ok": True}

    def opencode_agent_detail(self, *, agent_id: str, include_deleted: bool = False) -> dict[str, Any]:
        clean_id = normalize_agent_id(agent_id)
        with self._read_session() as connection:
            return self._opencode_agent_dict(self._opencode_agent_row(connection, clean_id, include_deleted=include_deleted))

    def enabled_opencode_agent_for_run(self, *, agent_id: str) -> dict[str, Any]:
        clean_id = normalize_agent_id(agent_id)
        with self._read_session() as connection:
            row = self._opencode_agent_row(connection, clean_id, include_deleted=False)
            if not row["enabled"]:
                raise InvariantError(f"Opencode Agent is disabled: {clean_id}")
            return self._opencode_agent_dict(row)

    def _clean_opencode_agent_payload(self, payload: dict[str, Any], *, actor: str, created_at, require_id: bool) -> dict[str, Any]:
        row = {
            "name": normalize_agent_name(str(payload.get("name") or "")),
            "description": normalize_agent_description(payload.get("description")),
            "prompt": normalize_agent_prompt(str(payload.get("prompt") or "")),
            "enabled": bool(payload.get("enabled", True)),
            "permission": normalize_agent_permission(payload.get("permission")),
            "provider_id": normalize_agent_optional_text(payload.get("provider_id"), label="Agent provider_id"),
            "model_id": normalize_agent_optional_text(payload.get("model_id"), label="Agent model_id"),
            "temperature": normalize_agent_temperature(payload.get("temperature")),
            "steps": normalize_agent_steps(payload.get("steps")),
            "updated_at": created_at,
            "updated_by": actor,
        }
        if require_id:
            row["id"] = normalize_agent_id(str(payload.get("id") or ""))
            row["created_at"] = created_at
            row["created_by"] = actor
        return row

    def _opencode_agent_row(self, connection, agent_id: str, *, include_deleted: bool):
        query = orm.select_entity(orm.OpencodeAgent).where(orm.OpencodeAgent.id == agent_id)
        if not include_deleted:
            query = query.where(orm.OpencodeAgent.deleted_at.is_(None))
        row = connection.execute(query).mappings().one_or_none()
        if row is None:
            raise NotFoundError(f"Opencode Agent not found: {agent_id}")
        return row

    def _opencode_agent_dict(self, row) -> dict[str, Any]:
        return self._row_dict(row)

    def _audit_opencode_agent(self, connection, *, action: str, agent_id: str, actor: str, payload: dict[str, Any]) -> None:
        connection.execute(
            insert(orm.AuditEvent).values(
                id=new_id("audit"),
                actor_ref=actor,
                action=action,
                resource_type="opencode_agent",
                resource_id=agent_id,
                payload=payload,
                created_at=utc_now(),
            )
        )
