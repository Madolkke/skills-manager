from __future__ import annotations

from typing import Any

from sqlalchemy import insert, update

from skillhub.domain.errors import InvariantError, NotFoundError
from skillhub.domain.models import new_id, utc_now
from skillhub.infrastructure.db import tables
from .results import CreateEvalCaseResult, CreateEvalCasesBatchResult, CreatedEvalCaseResult


class EvalCaseCommandMixin:
    def update_eval_case_title(self, *, case_id: str, title: str) -> dict[str, Any]:
        updated_at = utc_now()
        with self.engine.begin() as connection:
            self._eval_case_row(connection, case_id)
            connection.execute(
                update(tables.eval_cases)
                .where(tables.eval_cases.c.id == case_id)
                .values(title=title, updated_at=updated_at)
            )
            return self._row_dict(self._eval_case_row(connection, case_id))

    def archive_eval_case(self, *, case_id: str, actor: str) -> CreateEvalCaseResult:
        updated_at = utc_now()
        with self.engine.begin() as connection:
            eval_case = self._eval_case_row(connection, case_id)
            skill_id = eval_case["skill_id"]
            eval_set = self._primary_eval_set_row(connection, skill_id)
            current_eval_set_version = self._eval_set_version_row(connection, eval_set["current_version_id"])
            connection.execute(
                update(tables.eval_cases)
                .where(tables.eval_cases.c.id == case_id)
                .values(lifecycle_status="archived", updated_at=updated_at)
            )
            next_case_version_ids = [
                case_version_id
                for case_version_id in self._eval_set_case_version_ids(connection, current_eval_set_version["id"])
                if self._eval_case_version_row(connection, case_version_id)["case_id"] != case_id
            ]
            eval_set_version_id = self._update_current_eval_set_cases(
                connection,
                skill_id=skill_id,
                eval_set_id=eval_set["id"],
                current_eval_set_version_id=current_eval_set_version["id"],
                case_version_ids=next_case_version_ids,
                updated_at=updated_at,
                actor=actor,
            )
        return CreateEvalCaseResult(skill_id, eval_set["id"], eval_set_version_id, case_id, eval_case["current_version_id"], "", "")

    def create_eval_case(
        self,
        *,
        skill_id: str,
        title: str,
        input_text: str,
        expected_output: str,
        actor: str,
        notes: str | None = None,
        eval_set_version_display_name: str | None = None,
    ) -> CreateEvalCaseResult:
        created_at = utc_now()
        eval_case_id = new_id("case")
        eval_case_version_id = new_id("casever")
        with self.engine.begin() as connection:
            eval_set = self._primary_eval_set_row(connection, skill_id)
            current_eval_set_version = self._eval_set_version_row(connection, eval_set["current_version_id"])
            input_artifact_id = self._insert_text_artifact(
                connection, kind="eval_input", namespace=skill_id, content=input_text, actor=actor, created_at=created_at
            )
            expected_output_artifact_id = self._insert_text_artifact(
                connection,
                kind="expected_output",
                namespace=skill_id,
                content=expected_output,
                actor=actor,
                created_at=created_at,
            )
            connection.execute(
                insert(tables.eval_cases).values(
                    id=eval_case_id,
                    skill_id=skill_id,
                    title=title,
                    current_version_id=None,
                    lifecycle_status="active",
                    created_at=created_at,
                    updated_at=created_at,
                )
            )
            connection.execute(
                insert(tables.eval_case_versions).values(
                    id=eval_case_version_id,
                    skill_id=skill_id,
                    case_id=eval_case_id,
                    version_number=1,
                    input_artifact_id=input_artifact_id,
                    expected_output_artifact_id=expected_output_artifact_id,
                    notes=notes,
                    created_at=created_at,
                    created_by=actor,
                )
            )
            connection.execute(
                update(tables.eval_cases)
                .where(tables.eval_cases.c.id == eval_case_id)
                .values(current_version_id=eval_case_version_id, updated_at=created_at)
            )
            eval_set_version_id = self._update_current_eval_set_cases(
                connection,
                skill_id=skill_id,
                eval_set_id=eval_set["id"],
                current_eval_set_version_id=current_eval_set_version["id"],
                case_version_ids=[
                    *self._eval_set_case_version_ids(connection, current_eval_set_version["id"]),
                    eval_case_version_id,
                ],
                updated_at=created_at,
                actor=actor,
                display_name=eval_set_version_display_name,
            )
        return CreateEvalCaseResult(
            skill_id,
            eval_set["id"],
            eval_set_version_id,
            eval_case_id,
            eval_case_version_id,
            input_artifact_id,
            expected_output_artifact_id,
        )

    def create_eval_cases_batch(self, *, skill_id: str, cases: list[dict[str, Any]], actor: str) -> CreateEvalCasesBatchResult:
        if not cases:
            raise InvariantError("At least one eval case is required.")
        created_at = utc_now()
        created_cases: list[CreatedEvalCaseResult] = []
        with self.engine.begin() as connection:
            eval_set = self._primary_eval_set_row(connection, skill_id)
            current_eval_set_version = self._eval_set_version_row(connection, eval_set["current_version_id"])
            for item in cases:
                title = self._required_text(item, "title")
                input_text = self._required_text(item, "input_text")
                expected_output = self._required_text(item, "expected_output")
                if not title or not input_text or not expected_output:
                    raise InvariantError("Each eval case requires title, input_text, and expected_output.")
                eval_case_id = new_id("case")
                eval_case_version_id = new_id("casever")
                input_artifact_id = self._insert_text_artifact(
                    connection, kind="eval_input", namespace=skill_id, content=input_text, actor=actor, created_at=created_at
                )
                expected_output_artifact_id = self._insert_text_artifact(
                    connection,
                    kind="expected_output",
                    namespace=skill_id,
                    content=expected_output,
                    actor=actor,
                    created_at=created_at,
                )
                connection.execute(
                    insert(tables.eval_cases).values(
                        id=eval_case_id,
                        skill_id=skill_id,
                        title=title,
                        current_version_id=None,
                        lifecycle_status="active",
                        created_at=created_at,
                        updated_at=created_at,
                    )
                )
                connection.execute(
                    insert(tables.eval_case_versions).values(
                        id=eval_case_version_id,
                        skill_id=skill_id,
                        case_id=eval_case_id,
                        version_number=1,
                        input_artifact_id=input_artifact_id,
                        expected_output_artifact_id=expected_output_artifact_id,
                        notes=item.get("notes"),
                        created_at=created_at,
                        created_by=actor,
                    )
                )
                connection.execute(
                    update(tables.eval_cases)
                    .where(tables.eval_cases.c.id == eval_case_id)
                    .values(current_version_id=eval_case_version_id, updated_at=created_at)
                )
                created_cases.append(
                    CreatedEvalCaseResult(eval_case_id, eval_case_version_id, input_artifact_id, expected_output_artifact_id)
                )
            eval_set_version_id = self._update_current_eval_set_cases(
                connection,
                skill_id=skill_id,
                eval_set_id=eval_set["id"],
                current_eval_set_version_id=current_eval_set_version["id"],
                case_version_ids=[
                    *self._eval_set_case_version_ids(connection, current_eval_set_version["id"]),
                    *[item.eval_case_version_id for item in created_cases],
                ],
                updated_at=created_at,
                actor=actor,
            )
        return CreateEvalCasesBatchResult(skill_id, eval_set["id"], eval_set_version_id, tuple(created_cases))

    def create_eval_case_version(
        self,
        *,
        case_id: str,
        input_text: str,
        expected_output: str,
        actor: str,
        notes: str | None = None,
        eval_set_version_display_name: str | None = None,
        make_current: bool = True,
    ) -> CreateEvalCaseResult:
        created_at = utc_now()
        eval_case_version_id = new_id("casever")
        with self.engine.begin() as connection:
            eval_case = self._eval_case_row(connection, case_id)
            skill_id = eval_case["skill_id"]
            version_number = self._next_eval_case_version_number(connection, case_id)
            input_artifact_id = self._insert_text_artifact(
                connection, kind="eval_input", namespace=skill_id, content=input_text, actor=actor, created_at=created_at
            )
            expected_output_artifact_id = self._insert_text_artifact(
                connection,
                kind="expected_output",
                namespace=skill_id,
                content=expected_output,
                actor=actor,
                created_at=created_at,
            )
            connection.execute(
                insert(tables.eval_case_versions).values(
                    id=eval_case_version_id,
                    skill_id=skill_id,
                    case_id=case_id,
                    version_number=version_number,
                    input_artifact_id=input_artifact_id,
                    expected_output_artifact_id=expected_output_artifact_id,
                    notes=notes,
                    created_at=created_at,
                    created_by=actor,
                )
            )
            eval_set = self._primary_eval_set_row(connection, skill_id)
            eval_set_version_id = eval_set["current_version_id"]
            if make_current:
                connection.execute(
                    update(tables.eval_cases)
                    .where(tables.eval_cases.c.id == case_id)
                    .values(current_version_id=eval_case_version_id, updated_at=created_at)
                )
                current_eval_set_version = self._eval_set_version_row(connection, eval_set["current_version_id"])
                eval_set_version_id = self._update_current_eval_set_cases(
                    connection,
                    skill_id=skill_id,
                    eval_set_id=eval_set["id"],
                    current_eval_set_version_id=current_eval_set_version["id"],
                    case_version_ids=[
                        eval_case_version_id
                        if self._eval_case_version_row(connection, item)["case_id"] == case_id
                        else item
                        for item in self._eval_set_case_version_ids(connection, current_eval_set_version["id"])
                    ],
                    updated_at=created_at,
                    actor=actor,
                    display_name=eval_set_version_display_name,
                )
        return CreateEvalCaseResult(
            skill_id, eval_set["id"], eval_set_version_id, case_id, eval_case_version_id, input_artifact_id, expected_output_artifact_id
        )

    def restore_eval_case_version(
        self,
        *,
        case_id: str,
        source_case_version_id: str,
        actor: str,
        notes: str | None = None,
    ) -> CreateEvalCaseResult:
        with self.engine.connect() as connection:
            eval_case = self._eval_case_row(connection, case_id)
            if eval_case["lifecycle_status"] != "active":
                raise InvariantError("Archived eval cases cannot be restored.")
            source_case_version = self._eval_case_version_row(connection, source_case_version_id)
            if source_case_version["case_id"] != case_id:
                raise NotFoundError(f"EvalCaseVersion not found for case: {source_case_version_id}")
            source_detail = self._case_version_detail(connection, source_case_version)
        input_text = source_detail["input_artifact"].get("content_text")
        expected_output = source_detail["expected_output_artifact"].get("content_text")
        if input_text is None or expected_output is None:
            raise InvariantError("Only text eval case versions can be restored.")
        return self.create_eval_case_version(
            case_id=case_id,
            input_text=input_text,
            expected_output=expected_output,
            actor=actor,
            notes=notes if notes is not None else f"Restored from case v{source_case_version['version_number']}.",
            make_current=True,
        )
