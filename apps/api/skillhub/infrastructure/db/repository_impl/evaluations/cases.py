from __future__ import annotations

from typing import Any

from sqlalchemy import insert, update

from skillhub.application.eval_assertion_templates import normalize_assertion_step
from skillhub.domain.errors import InvariantError, NotFoundError
from skillhub.domain.models import new_id, utc_now
from skillhub.infrastructure.db import tables
from skillhub.infrastructure.db.repository_impl.shared.results import CreateEvalCaseResult, CreateEvalCasesBatchResult, CreatedEvalCaseResult


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

    def create_eval_case(
        self,
        *,
        skill_id: str,
        eval_set_id: str | None = None,
        title: str,
        steps: list[dict[str, Any]] | None = None,
        actor: str,
        workspace_name: str | None = None,
        workspace_base64: str | None = None,
        runner_config: dict[str, Any] | None = None,
        notes: str | None = None,
        input_text: str | None = None,
        expected_output: str | None = None,
        attachment_name: str | None = None,
        attachment_base64: str | None = None,
    ) -> CreateEvalCaseResult:
        created_at = utc_now()
        eval_case_id = new_id("case")
        eval_case_version_id = new_id("casever")
        clean_steps = self._case_steps(steps or self._legacy_step(input_text, expected_output))
        clean_runner_config = self._case_runner_config(runner_config)
        workspace_name = workspace_name or attachment_name
        workspace_base64 = workspace_base64 or attachment_base64
        with self.engine.begin() as connection:
            eval_set = self._eval_set_for_case_write(connection, skill_id=skill_id, eval_set_id=eval_set_id)
            workspace_artifact_id = self._create_case_workspace(
                connection,
                skill_id=skill_id,
                actor=actor,
                workspace_name=workspace_name,
                workspace_base64=workspace_base64,
                created_at=created_at,
            )
            connection.execute(
                insert(tables.eval_cases).values(
                    id=eval_case_id,
                    skill_id=skill_id,
                    title=title,
                    current_version_id=None,
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
                    workspace_artifact_id=workspace_artifact_id,
                    steps=clean_steps,
                    runner_config=clean_runner_config,
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
            eval_set_id = self._update_eval_set_cases(
                connection,
                skill_id=skill_id,
                eval_set_id=eval_set["id"],
                case_ids=[*self._eval_set_case_ids(connection, eval_set["id"]), eval_case_id],
                updated_at=created_at,
            )
        return CreateEvalCaseResult(skill_id, eval_set_id, eval_case_id, eval_case_version_id, workspace_artifact_id)

    def create_eval_cases_batch(self, *, skill_id: str, cases: list[dict[str, Any]], actor: str, eval_set_id: str | None = None) -> CreateEvalCasesBatchResult:
        if not cases:
            raise InvariantError("At least one eval case is required.")
        created_at = utc_now()
        created_cases: list[CreatedEvalCaseResult] = []
        with self.engine.begin() as connection:
            eval_set = self._eval_set_for_case_write(connection, skill_id=skill_id, eval_set_id=eval_set_id)
            for item in cases:
                title = self._required_text(item, "title")
                if not title:
                    raise InvariantError("Each eval case requires title.")
                eval_case_id = new_id("case")
                eval_case_version_id = new_id("casever")
                workspace_artifact_id = self._create_case_workspace(
                    connection,
                    skill_id=skill_id,
                    actor=actor,
                    workspace_name=item.get("workspace_name"),
                    workspace_base64=item.get("workspace_base64"),
                    created_at=created_at,
                )
                connection.execute(
                    insert(tables.eval_cases).values(
                        id=eval_case_id,
                        skill_id=skill_id,
                        title=title,
                        current_version_id=None,
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
                        workspace_artifact_id=workspace_artifact_id,
                        steps=self._case_steps(item.get("steps") or []),
                        runner_config=self._case_runner_config(item.get("runner_config")),
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
                created_cases.append(CreatedEvalCaseResult(eval_case_id, eval_case_version_id, workspace_artifact_id))
            eval_set_id = self._update_eval_set_cases(
                connection,
                skill_id=skill_id,
                eval_set_id=eval_set["id"],
                case_ids=[*self._eval_set_case_ids(connection, eval_set["id"]), *[item.eval_case_id for item in created_cases]],
                updated_at=created_at,
            )
        return CreateEvalCasesBatchResult(skill_id, eval_set_id, tuple(created_cases))

    def create_eval_case_version(
        self,
        *,
        case_id: str,
        eval_set_id: str | None = None,
        steps: list[dict[str, Any]] | None = None,
        actor: str,
        workspace_name: str | None = None,
        workspace_base64: str | None = None,
        preserve_workspace: bool = True,
        runner_config: dict[str, Any] | None = None,
        notes: str | None = None,
        make_current: bool = True,
        input_text: str | None = None,
        expected_output: str | None = None,
        attachment_name: str | None = None,
        attachment_base64: str | None = None,
    ) -> CreateEvalCaseResult:
        created_at = utc_now()
        eval_case_version_id = new_id("casever")
        workspace_name = workspace_name or attachment_name
        workspace_base64 = workspace_base64 or attachment_base64
        with self.engine.begin() as connection:
            eval_case = self._eval_case_row(connection, case_id)
            skill_id = eval_case["skill_id"]
            eval_set = self._eval_set_for_case_write(connection, skill_id=skill_id, eval_set_id=eval_set_id)
            self._require_eval_set_contains_case(connection, eval_set_id=eval_set["id"], case_id=case_id)
            version_number = self._next_eval_case_version_number(connection, case_id)
            workspace_artifact_id = self._create_case_workspace(
                connection,
                skill_id=skill_id,
                actor=actor,
                workspace_name=workspace_name,
                workspace_base64=workspace_base64,
                created_at=created_at,
            )
            if workspace_artifact_id is None and preserve_workspace and eval_case["current_version_id"]:
                workspace_artifact_id = self._eval_case_version_row(connection, eval_case["current_version_id"])["workspace_artifact_id"]
            connection.execute(
                insert(tables.eval_case_versions).values(
                    id=eval_case_version_id,
                    skill_id=skill_id,
                    case_id=case_id,
                    version_number=version_number,
                    workspace_artifact_id=workspace_artifact_id,
                    steps=self._case_steps(steps or self._legacy_step(input_text, expected_output)),
                    runner_config=self._case_runner_config(runner_config),
                    notes=notes,
                    created_at=created_at,
                    created_by=actor,
                )
            )
            if make_current:
                connection.execute(
                    update(tables.eval_cases)
                    .where(tables.eval_cases.c.id == case_id)
                    .values(current_version_id=eval_case_version_id, updated_at=created_at)
                )
        return CreateEvalCaseResult(skill_id, eval_set["id"], case_id, eval_case_version_id, workspace_artifact_id)

    def restore_eval_case_version(
        self,
        *,
        case_id: str,
        eval_set_id: str | None = None,
        source_case_version_id: str,
        actor: str,
        notes: str | None = None,
    ) -> CreateEvalCaseResult:
        with self.engine.connect() as connection:
            self._eval_case_row(connection, case_id)
            source_case_version = self._eval_case_version_row(connection, source_case_version_id)
            if source_case_version["case_id"] != case_id:
                raise NotFoundError(f"EvalCaseVersion not found for case: {source_case_version_id}")
        return self.create_eval_case_version(
            case_id=case_id,
            eval_set_id=eval_set_id,
            steps=list(source_case_version["steps"]),
            workspace_name=None,
            workspace_base64=None,
            preserve_workspace=True,
            runner_config=dict(source_case_version["runner_config"] or {}),
            actor=actor,
            notes=notes if notes is not None else f"Restored from case v{source_case_version['version_number']}.",
            make_current=True,
        )

    def _case_steps(self, steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not steps:
            raise InvariantError("Eval case requires at least one step.")
        return [normalize_assertion_step(step, index) for index, step in enumerate(steps)]

    def _legacy_step(self, input_text: str | None, expected_output: str | None) -> list[dict[str, Any]]:
        if input_text is None and expected_output is None:
            return []
        return [
            {
                "title": "步骤 1",
                "input": input_text or "",
                "assertion_template_id": "agent_output_contains",
                "assertion_params": {"text": expected_output or ""},
            }
        ]

    def _case_runner_config(self, value: dict[str, Any] | None) -> dict[str, Any]:
        raw = dict(value or {})
        provider = str(raw.get("model_provider_id") or "").strip() or None
        model = str(raw.get("model_id") or "").strip() or None
        if bool(provider) != bool(model):
            raise InvariantError("Eval case runner model requires both provider and model.")
        return {
            "model_provider_id": provider,
            "model_id": model,
            "timeout_seconds": raw.get("timeout_seconds"),
        }

    def _eval_set_for_case_write(self, connection, *, skill_id: str, eval_set_id: str | None):
        eval_set = self._eval_set_row(connection, eval_set_id) if eval_set_id else self._primary_eval_set_row(connection, skill_id)
        if eval_set["skill_id"] != skill_id:
            raise InvariantError("Eval case and eval set must belong to the same skill.")
        return eval_set
