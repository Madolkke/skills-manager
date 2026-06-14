from __future__ import annotations

from typing import Any

from sqlalchemy import desc, insert, select, update

from skillhub.application.run_comparison import build_run_case_comparisons, build_run_comparison_summary
from skillhub.application.run_matrix import build_eval_run_matrix
from skillhub.domain.errors import InvariantError
from skillhub.domain.models import new_id, utc_now
from skillhub.infrastructure.db import tables


class RunHistoryQueryMixin:
    def list_eval_runs_for_skill(
        self,
        *,
        skill_id: str,
        skill_version_id: str | None = None,
        eval_set_id: str | None = None,
        strategy: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        with self.engine.connect() as connection:
            skill = self._skill_row(connection, skill_id)
            rows = self._filtered_eval_run_rows(connection, skill_id, skill_version_id, eval_set_id, strategy, status, limit)
            runs = [self._eval_run_context_row(connection, row, include_accepted=True) for row in rows]
        return {"skill": self._row_dict(skill), "runs": runs}

    def eval_run_matrix_for_skill(
        self,
        *,
        skill_id: str,
        skill_version_id: str | None = None,
        eval_set_id: str | None = None,
        strategy: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        with self.engine.connect() as connection:
            skill = self._skill_row(connection, skill_id)
            rows = self._filtered_eval_run_rows(connection, skill_id, skill_version_id, eval_set_id, strategy, status, limit)
            runs = [self._eval_run_context_row(connection, row, include_accepted=False) for row in rows]
            eval_set_cases_by_run = {row["id"]: self._eval_set_cases(connection, row["eval_set_id"]) for row in rows}
            results_by_run = {
                row["id"]: [
                    self._row_dict(result)
                    for result in connection.execute(select(tables.case_results).where(tables.case_results.c.run_id == row["id"]))
                    .mappings()
                    .all()
                ]
                for row in rows
            }
        return build_eval_run_matrix(skill=self._row_dict(skill), runs=runs, eval_set_cases_by_run=eval_set_cases_by_run, results_by_run=results_by_run)

    def compare_eval_runs(self, *, baseline_run_id: str, candidate_run_id: str) -> dict[str, Any]:
        with self.engine.connect() as connection:
            baseline_run = self._eval_run_row(connection, baseline_run_id)
            candidate_run = self._eval_run_row(connection, candidate_run_id)
            if baseline_run["skill_id"] != candidate_run["skill_id"]:
                raise InvariantError("Run comparison requires runs from the same skill.")
            if baseline_run["eval_set_id"] != candidate_run["eval_set_id"]:
                raise InvariantError("Run comparison requires the same eval set.")
            if baseline_run["status"] != "finished" or candidate_run["status"] != "finished":
                raise InvariantError("Run comparison requires finished runs.")
            skill = self._skill_row(connection, baseline_run["skill_id"])
            eval_set = self._eval_set_row(connection, baseline_run["eval_set_id"])
            baseline_version = self._skill_version_row(connection, baseline_run["skill_version_id"])
            candidate_version = self._skill_version_row(connection, candidate_run["skill_version_id"])
            case_comparisons, comparison_summary = build_run_case_comparisons(
                eval_set_cases=self._eval_set_cases(connection, eval_set["id"]),
                baseline_results=self._case_results_by_case_version(connection, baseline_run["id"]),
                candidate_results=self._case_results_by_case_version(connection, candidate_run["id"]),
            )
            return {
                "skill": self._row_dict(skill),
                "eval_set": self._row_dict(eval_set),
                "baseline": {"eval_run": self._row_dict(baseline_run), "skill_version": self._row_dict(baseline_version)},
                "candidate": {"eval_run": self._row_dict(candidate_run), "skill_version": self._row_dict(candidate_version)},
                "summary": build_run_comparison_summary(
                    baseline_summary=baseline_run["summary"],
                    candidate_summary=candidate_run["summary"],
                    comparison_summary=comparison_summary,
                ),
                "case_comparisons": case_comparisons,
                "candidate_accepted_verification": self._accepted_verification_for_eval_run(connection, candidate_run["id"]),
            }

    def accept_eval_run_verification(self, *, eval_run_id: str, note: str, actor: str) -> dict[str, Any]:
        accepted_at = utc_now()
        with self.engine.begin() as connection:
            eval_run = self._eval_run_row(connection, eval_run_id)
            if eval_run["status"] != "finished":
                raise InvariantError("Accepted verification requires a finished eval run.")
            self._require_skill_permission(connection, skill_id=eval_run["skill_id"], actor=actor, permission="verification.accept")
            skill_version = self._skill_version_row(connection, eval_run["skill_version_id"])
            eval_set = self._eval_set_row(connection, eval_run["eval_set_id"])
            if skill_version["skill_id"] != eval_run["skill_id"] or eval_set["skill_id"] != eval_run["skill_id"]:
                raise InvariantError("Accepted verification requires same-skill records.")

            values = {
                "skill_id": eval_run["skill_id"],
                "skill_version_id": skill_version["id"],
                "eval_set_id": eval_set["id"],
                "run_context_hash": eval_run["run_context_hash"],
                "eval_run_id": eval_run["id"],
                "note": note.strip(),
                "created_at": accepted_at,
                "created_by": actor,
            }
            existing = self._accepted_verification_for_context(
                connection,
                skill_id=eval_run["skill_id"],
                skill_version_id=skill_version["id"],
                eval_set_id=eval_set["id"],
                run_context_hash=eval_run["run_context_hash"],
            )
            if existing is None:
                accepted_id = new_id("accepted")
                connection.execute(insert(tables.accepted_verifications).values(id=accepted_id, **values))
            else:
                accepted_id = existing["id"]
                connection.execute(update(tables.accepted_verifications).where(tables.accepted_verifications.c.id == accepted_id).values(**values))
            connection.execute(
                insert(tables.audit_events).values(
                    id=new_id("audit"),
                    actor_ref=actor,
                    action="eval_run.accepted_verification_set",
                    resource_type="eval_run",
                    resource_id=eval_run["id"],
                    payload={
                        "accepted_verification_id": accepted_id,
                        "eval_run_id": eval_run["id"],
                        "skill_version_id": skill_version["id"],
                        "eval_set_id": eval_set["id"],
                        "run_context_hash": eval_run["run_context_hash"],
                    },
                    created_at=accepted_at,
                )
            )
            accepted = self._accepted_verification_row(connection, accepted_id)
        return self._row_dict(accepted)

    def _filtered_eval_run_rows(
        self,
        connection,
        skill_id: str,
        skill_version_id: str | None,
        eval_set_id: str | None,
        strategy: str | None,
        status: str | None,
        limit: int,
    ):
        query = select(tables.eval_runs).where(tables.eval_runs.c.skill_id == skill_id)
        if skill_version_id:
            query = query.where(tables.eval_runs.c.skill_version_id == skill_version_id)
        if eval_set_id:
            query = query.where(tables.eval_runs.c.eval_set_id == eval_set_id)
        if strategy:
            query = query.where(tables.eval_runs.c.strategy == strategy)
        if status:
            query = query.where(tables.eval_runs.c.status == status)
        return (
            connection.execute(query.order_by(desc(tables.eval_runs.c.created_at), desc(tables.eval_runs.c.id)).limit(max(1, min(limit, 200))))
            .mappings()
            .all()
        )

    def _eval_run_context_row(self, connection, run, *, include_accepted: bool) -> dict[str, Any]:
        skill_version = self._skill_version_row(connection, run["skill_version_id"])
        eval_set = self._eval_set_row(connection, run["eval_set_id"])
        row = {
            "eval_run": self._row_dict(run),
            "skill_version": self._row_dict(skill_version),
            "eval_set": self._row_dict(eval_set),
        }
        if include_accepted:
            row["accepted_verification"] = self._accepted_verification_for_eval_run(connection, run["id"])
        return row

    def _latest_finished_run(self, connection, *, skill_version_id: str, eval_set_id: str):
        return (
            connection.execute(
                select(tables.eval_runs)
                .where(tables.eval_runs.c.skill_version_id == skill_version_id)
                .where(tables.eval_runs.c.eval_set_id == eval_set_id)
                .where(tables.eval_runs.c.status == "finished")
                .order_by(desc(tables.eval_runs.c.created_at), desc(tables.eval_runs.c.id))
                .limit(1)
            )
            .mappings()
            .one_or_none()
        )

    def _case_results_by_case_version(self, connection, run_id: str) -> dict[str, bool]:
        return {
            row["case_version_id"]: row["passed"]
            for row in connection.execute(
                select(tables.case_results.c.case_version_id, tables.case_results.c.passed).where(tables.case_results.c.run_id == run_id)
            )
            .mappings()
            .all()
        }
