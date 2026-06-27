from __future__ import annotations

from typing import Any

from sqlalchemy import insert, select, update
from sqlalchemy.exc import IntegrityError

from skillhub.models.rules.eval_sets import eval_set_name_conflict, normalize_eval_set_description, normalize_eval_set_name
from skillhub.models.errors import FieldError, FieldInvariantError, InvariantError
from skillhub.models.entities import new_id, utc_now
from skillhub.models.schema import tables


class EvalSetCommandMixin:
    def create_eval_set(self, *, skill_id: str, name: str, description: str = "", actor: str | None = None) -> dict[str, Any]:
        """Legacy store facade; EvaluationService owns normal input normalization."""
        return self.insert_eval_set(
            skill_id=skill_id,
            name=normalize_eval_set_name(name),
            description=normalize_eval_set_description(description),
            actor=actor,
        )

    def insert_eval_set(self, *, skill_id: str, name: str, description: str, actor: str | None = None) -> dict[str, Any]:
        created_at = utc_now()
        eval_set_id = new_id("evalset")
        try:
            with self.engine.begin() as connection:
                self._skill_row(connection, skill_id)
                if actor is not None:
                    self._require_skill_permission(connection, skill_id=skill_id, actor=actor, permission="eval.manage")
                connection.execute(
                    insert(tables.eval_sets).values(
                        id=eval_set_id,
                        skill_id=skill_id,
                        name=name,
                        description=description,
                        created_at=created_at,
                        updated_at=created_at,
                    )
                )
                return self._row_dict(self._eval_set_row(connection, eval_set_id))
        except IntegrityError as exc:
            raise eval_set_name_conflict(name) from exc

    def update_eval_set(self, *, eval_set_id: str, name: str, description: str = "", actor: str | None = None) -> dict[str, Any]:
        """Legacy store facade; EvaluationService owns normal input normalization."""
        return self.rename_eval_set(
            eval_set_id=eval_set_id,
            name=normalize_eval_set_name(name),
            description=normalize_eval_set_description(description),
            actor=actor,
        )

    def rename_eval_set(self, *, eval_set_id: str, name: str, description: str, actor: str | None = None) -> dict[str, Any]:
        updated_at = utc_now()
        try:
            with self.engine.begin() as connection:
                eval_set = self._eval_set_row(connection, eval_set_id)
                if actor is not None:
                    self._require_skill_permission(connection, skill_id=eval_set["skill_id"], actor=actor, permission="eval.manage")
                connection.execute(
                    update(tables.eval_sets)
                    .where(tables.eval_sets.c.id == eval_set_id)
                    .values(name=name, description=description, updated_at=updated_at)
                )
                return self._row_dict(self._eval_set_row(connection, eval_set_id))
        except IntegrityError as exc:
            raise eval_set_name_conflict(name) from exc

    def list_eval_cases_for_skill(self, *, skill_id: str, exclude_eval_set_id: str | None = None) -> list[dict[str, Any]]:
        with self.engine.connect() as connection:
            self._skill_row(connection, skill_id)
            excluded: set[str] = set()
            if exclude_eval_set_id:
                eval_set = self._eval_set_row(connection, exclude_eval_set_id)
                if eval_set["skill_id"] != skill_id:
                    raise InvariantError("Eval set and skill must match.")
                excluded = set(self._eval_set_case_ids(connection, exclude_eval_set_id))
            rows = (
                connection.execute(
                    select(tables.eval_cases)
                    .where(tables.eval_cases.c.skill_id == skill_id)
                    .order_by(tables.eval_cases.c.updated_at.desc(), tables.eval_cases.c.title)
                )
                .mappings()
                .all()
            )
            cases = []
            for eval_case in rows:
                if eval_case["id"] in excluded or not eval_case["current_version_id"]:
                    continue
                case_version = self._eval_case_version_row(connection, eval_case["current_version_id"])
                cases.append({"case": self._row_dict(eval_case), "case_version": self._case_version_detail(connection, case_version)})
            return cases

    def add_eval_case_to_set(self, *, eval_set_id: str, case_id: str, position: int | None = None, actor: str | None = None) -> dict[str, Any]:
        updated_at = utc_now()
        with self.engine.begin() as connection:
            eval_set = self._eval_set_row(connection, eval_set_id)
            if actor is not None:
                self._require_skill_permission(connection, skill_id=eval_set["skill_id"], actor=actor, permission="eval.manage")
            eval_case = self._eval_case_row(connection, case_id)
            if eval_case["skill_id"] != eval_set["skill_id"]:
                raise InvariantError("Eval case and eval set must belong to the same skill.")
            if not eval_case["current_version_id"]:
                raise InvariantError("Eval case has no current version.")
            case_ids = self._eval_set_case_ids(connection, eval_set_id)
            if case_id in case_ids:
                raise self._eval_case_already_in_set()
            insert_at = len(case_ids) if position is None else max(0, min(position, len(case_ids)))
            next_case_ids = [*case_ids[:insert_at], case_id, *case_ids[insert_at:]]
            self._update_eval_set_cases(
                connection,
                skill_id=eval_set["skill_id"],
                eval_set_id=eval_set_id,
                case_ids=next_case_ids,
                updated_at=updated_at,
            )
        return self.eval_set_detail(eval_set_id)

    def remove_eval_case_from_set(self, *, eval_set_id: str, case_id: str, actor: str | None = None) -> dict[str, Any]:
        updated_at = utc_now()
        with self.engine.begin() as connection:
            eval_set = self._eval_set_row(connection, eval_set_id)
            if actor is not None:
                self._require_skill_permission(connection, skill_id=eval_set["skill_id"], actor=actor, permission="eval.manage")
            case_ids = self._eval_set_case_ids(connection, eval_set_id)
            if case_id not in case_ids:
                raise self._eval_case_not_in_set(case_id)
            self._update_eval_set_cases(
                connection,
                skill_id=eval_set["skill_id"],
                eval_set_id=eval_set_id,
                case_ids=[item for item in case_ids if item != case_id],
                updated_at=updated_at,
            )
        return self.eval_set_detail(eval_set_id)

    def reorder_eval_set_cases(self, *, eval_set_id: str, case_ids: list[str], actor: str | None = None) -> dict[str, Any]:
        updated_at = utc_now()
        with self.engine.begin() as connection:
            eval_set = self._eval_set_row(connection, eval_set_id)
            if actor is not None:
                self._require_skill_permission(connection, skill_id=eval_set["skill_id"], actor=actor, permission="eval.manage")
            current_case_ids = self._eval_set_case_ids(connection, eval_set_id)
            if set(case_ids) != set(current_case_ids) or len(case_ids) != len(current_case_ids):
                raise FieldInvariantError(
                    "Eval set case order must include every current case exactly once.",
                    [FieldError(field="case_ids", message="排序列表必须包含当前测评集中的全部测试例，且不能重复。", code="eval_set.case_order_invalid")],
                )
            self._update_eval_set_cases(
                connection,
                skill_id=eval_set["skill_id"],
                eval_set_id=eval_set_id,
                case_ids=case_ids,
                updated_at=updated_at,
            )
        return self.eval_set_detail(eval_set_id)

    def _clean_eval_set_name(self, value: str) -> str:
        return normalize_eval_set_name(value)

    def _eval_set_name_conflict(self, name: str) -> FieldInvariantError:
        return eval_set_name_conflict(name)

    def _eval_case_already_in_set(self) -> FieldInvariantError:
        return FieldInvariantError(
            "Eval case already exists in this eval set.",
            [FieldError(field="case_id", message="该测试例已经在当前测评集中。", code="eval_set.case_exists")],
        )

    def _eval_case_not_in_set(self, case_id: str) -> FieldInvariantError:
        return FieldInvariantError(
            "Eval case is not in this eval set.",
            [FieldError(field="case_id", message=f"当前测评集中不存在该测试例：{case_id}", code="eval_set.case_missing")],
        )
