from __future__ import annotations

from typing import Any

from sqlalchemy import insert, update

from skillhub.models.entities import new_id, utc_now
from skillhub.models.operations.workflow_agent.helpers import WorkflowAgentHelperMixin
from skillhub.models.rules.workflow_agent import validate_debug_case_candidates
from skillhub.models.schema import orm


class WorkflowAgentProposalMixin(WorkflowAgentHelperMixin):
    def insert_workflow_agent_proposal(self, *, values: dict[str, Any]) -> dict[str, Any]:
        now = utc_now()
        row = {"id": new_id("workflow_agent_proposal"), **values, "created_at": now, "updated_at": now}
        with self._write_session() as session:
            session.execute(insert(orm.WorkflowAgentProposal).values(**row))
        return row

    def workflow_agent_proposal(self, *, proposal_id: str, actor: str) -> dict[str, Any]:
        with self._read_session() as session:
            row = self._workflow_agent_proposal_row(session, proposal_id)
            self._require_skill_permission(session, skill_id=row["skill_id"], actor=actor, permission="skill.edit")
            return self._agent_proposal_payload(row)

    def workflow_agent_proposal_for_run(self, *, run_id: str, actor: str) -> dict[str, Any] | None:
        with self._read_session() as session:
            run = self._workflow_agent_run_row(session, run_id)
            self._require_skill_permission(session, skill_id=run["skill_id"], actor=actor, permission="skill.edit")
            row = (
                session.execute(
                    orm.select_entity(orm.WorkflowAgentProposal)
                    .where(orm.WorkflowAgentProposal.run_id == run_id)
                    .limit(1)
                )
                .mappings()
                .one_or_none()
            )
            return self._agent_proposal_payload(row) if row is not None else None

    def apply_workflow_agent_proposal(self, *, proposal_id: str, cases: list[dict[str, Any]], actor: str) -> dict[str, Any]:
        with self._write_session() as session:
            proposal = self._workflow_agent_proposal_row(session, proposal_id, for_update=True)
            self._require_skill_permission(session, skill_id=proposal["skill_id"], actor=actor, permission="skill.edit")
            if proposal["status"] != "proposed":
                return {"proposal": self._agent_proposal_payload(proposal), "created_cases": [], "stale": proposal["status"] == "stale"}
            workflow = self._workflow_row(session, skill_id=proposal["skill_id"])
            if str(workflow["document_digest"]) != str(proposal["draft_digest"]):
                changes = {"status": "stale", "updated_at": utc_now()}
                session.execute(update(orm.WorkflowAgentProposal).where(orm.WorkflowAgentProposal.id == proposal_id).values(**changes))
                return {"proposal": {**self._agent_proposal_payload(proposal), **changes}, "created_cases": [], "stale": True}
            document = dict(workflow["document"])
            validate_debug_case_candidates(document, cases)
            now = utc_now()
            created = []
            for values in cases:
                row = {
                    "id": new_id("workflow_debug_case"),
                    "skill_id": proposal["skill_id"],
                    **values,
                    "created_by": actor,
                    "updated_by": actor,
                    "created_at": now,
                    "updated_at": now,
                }
                session.execute(insert(orm.WorkflowDebugCase).values(**row))
                created.append(row)
            result = {"case_ids": [row["id"] for row in created]}
            changes = {"status": "applied", "applied_result": result, "updated_at": now}
            session.execute(update(orm.WorkflowAgentProposal).where(orm.WorkflowAgentProposal.id == proposal_id).values(**changes))
            return {"proposal": {**self._agent_proposal_payload(proposal), **changes}, "created_cases": created, "stale": False}


__all__ = ["WorkflowAgentProposalMixin"]
