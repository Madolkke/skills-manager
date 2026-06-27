from __future__ import annotations

from typing import Any

from skillhub.models.rules.eval_cases import (
    legacy_eval_case_steps,
    normalize_eval_case_runner_config,
    normalize_eval_case_steps,
    normalize_eval_case_title,
)
from skillhub.models.errors import InvariantError
from skillhub.models.rules.eval_runs import decide_eval_run_aggregation, normalize_run_environment
from skillhub.models.rules.eval_sets import normalize_eval_set_description, normalize_eval_set_name
from skillhub.models.rules.eval_assertion_templates import list_assertion_templates
from skillhub.models.store import SkillHubStore
from skillhub.services.base import ServiceBase


class EvaluationService(ServiceBase[SkillHubStore]):
    def list_assertion_templates(self) -> list[dict[str, Any]]:
        return list_assertion_templates()

    def create_eval_set(self, *, skill_id: str, name: str, description: str | None, actor: str) -> Any:
        return self.store.insert_eval_set(
            skill_id=skill_id,
            name=normalize_eval_set_name(name),
            description=normalize_eval_set_description(description),
            actor=actor,
        )

    def update_eval_set(self, *, eval_set_id: str, name: str | None, description: str | None, actor: str) -> Any:
        return self.store.rename_eval_set(
            eval_set_id=eval_set_id,
            name=normalize_eval_set_name(name),
            description=normalize_eval_set_description(description),
            actor=actor,
        )

    def list_eval_cases_for_skill(self, *, skill_id: str, exclude_eval_set_id: str | None) -> Any:
        return self.store.list_eval_cases_for_skill(skill_id=skill_id, exclude_eval_set_id=exclude_eval_set_id)

    def add_eval_case_to_set(self, *, eval_set_id: str, case_id: str, position: int | None, actor: str) -> Any:
        return self.store.add_eval_case_to_set(eval_set_id=eval_set_id, case_id=case_id, position=position, actor=actor)

    def remove_eval_case_from_set(self, *, eval_set_id: str, case_id: str, actor: str) -> Any:
        return self.store.remove_eval_case_from_set(eval_set_id=eval_set_id, case_id=case_id, actor=actor)

    def reorder_eval_set_cases(self, *, eval_set_id: str, case_ids: list[str], actor: str) -> Any:
        return self.store.reorder_eval_set_cases(eval_set_id=eval_set_id, case_ids=case_ids, actor=actor)

    def create_eval_case(
        self,
        *,
        skill_id: str,
        eval_set_id: str,
        title: str,
        steps: list[dict[str, Any]],
        workspace_name: str | None,
        workspace_base64: str | None,
        runner_config: dict[str, Any],
        actor: str,
        notes: str | None,
    ) -> Any:
        clean_steps = normalize_eval_case_steps(steps or legacy_eval_case_steps(None, None))
        clean_title = normalize_eval_case_title(title)
        clean_runner_config = normalize_eval_case_runner_config(runner_config)
        snapshot = self.store.eval_case_create_snapshot(skill_id=skill_id, eval_set_id=eval_set_id, actor=actor)
        return self.store.insert_eval_case(
            skill_id=skill_id,
            eval_set_id=snapshot["eval_set_id"],
            title=clean_title,
            steps=clean_steps,
            workspace_name=workspace_name,
            workspace_base64=workspace_base64,
            runner_config=clean_runner_config,
            actor=actor,
            notes=notes,
        )

    def create_eval_cases_batch(self, *, skill_id: str, eval_set_id: str, cases: list[dict[str, Any]], actor: str) -> Any:
        if not cases:
            raise InvariantError("At least one eval case is required.")
        clean_cases = []
        for item in cases:
            clean_cases.append(
                {
                    **item,
                    "title": normalize_eval_case_title(item.get("title")),
                    "steps": normalize_eval_case_steps(item.get("steps") or []),
                    "runner_config": normalize_eval_case_runner_config(item.get("runner_config")),
                }
            )
        snapshot = self.store.eval_case_create_snapshot(skill_id=skill_id, eval_set_id=eval_set_id, actor=actor)
        return self.store.insert_eval_cases_batch(skill_id=skill_id, eval_set_id=snapshot["eval_set_id"], cases=clean_cases, actor=actor)

    def create_eval_case_version(
        self,
        *,
        case_id: str,
        eval_set_id: str,
        title: str,
        steps: list[dict[str, Any]],
        workspace_name: str | None,
        workspace_base64: str | None,
        preserve_workspace: bool,
        runner_config: dict[str, Any],
        actor: str,
        notes: str | None,
        make_current: bool,
    ) -> Any:
        clean_steps = normalize_eval_case_steps(steps or legacy_eval_case_steps(None, None))
        clean_title = normalize_eval_case_title(title)
        clean_runner_config = normalize_eval_case_runner_config(runner_config)
        snapshot = self.store.eval_case_version_create_snapshot(case_id=case_id, eval_set_id=eval_set_id, actor=actor)
        return self.store.insert_eval_case_version(
            case_id=case_id,
            skill_id=snapshot["skill_id"],
            eval_set_id=snapshot["eval_set_id"],
            title=clean_title,
            version_number=snapshot["next_version_number"],
            steps=clean_steps,
            workspace_name=workspace_name,
            workspace_base64=workspace_base64,
            preserve_workspace=preserve_workspace,
            runner_config=clean_runner_config,
            actor=actor,
            notes=notes,
            make_current=make_current,
        )

    def restore_eval_case_version(self, *, case_id: str, eval_set_id: str, source_case_version_id: str, actor: str, notes: str | None) -> Any:
        return self.store.restore_eval_case_version(
            case_id=case_id,
            eval_set_id=eval_set_id,
            source_case_version_id=source_case_version_id,
            actor=actor,
            notes=notes,
        )

    def enqueue_eval_case_run(
        self,
        *,
        skill_version_id: str,
        eval_set_id: str,
        case_version_id: str,
        actor: str,
        environment_tags: list[str],
        run_context: dict[str, Any],
    ) -> Any:
        tags, context, context_hash = normalize_run_environment(environment_tags, run_context)
        snapshot = self.store.eval_case_run_enqueue_snapshot(
            skill_version_id=skill_version_id,
            eval_set_id=eval_set_id,
            case_version_id=case_version_id,
            actor=actor,
            environment_tags=list(tags),
            run_context=context,
        )
        return self.store.insert_eval_case_run(
            skill_id=snapshot["skill_id"],
            skill_version_id=skill_version_id,
            eval_set_id=eval_set_id,
            case_version_id=case_version_id,
            actor=actor,
            environment_tags=list(tags),
            run_context=context,
            run_context_hash=context_hash,
        )

    def latest_eval_case_run_details(
        self,
        *,
        skill_version_id: str,
        eval_set_id: str,
        environment_tags: list[str],
        run_context: dict[str, Any],
    ) -> Any:
        tags, context, _context_hash = normalize_run_environment(environment_tags, run_context)
        return self.store.latest_eval_case_run_details(
            skill_version_id=skill_version_id,
            eval_set_id=eval_set_id,
            environment_tags=list(tags),
            run_context=context,
        )

    def eval_case_run_detail(self, *, eval_case_run_id: str) -> Any:
        return self.store.eval_case_run_detail(eval_case_run_id)

    def aggregate_eval_run(self, *, skill_version_id: str, eval_set_id: str, actor: str, environment_tags: list[str], run_context: dict[str, Any]) -> Any:
        tags, context, context_hash = normalize_run_environment(environment_tags, run_context)
        snapshot = self.store.eval_run_aggregation_snapshot(
            skill_version_id=skill_version_id,
            eval_set_id=eval_set_id,
            actor=actor,
            environment_tags=list(tags),
            run_context=context,
        )
        decision = decide_eval_run_aggregation(
            case_version_ids=snapshot["case_version_ids"],
            latest_case_runs=snapshot["latest_case_runs"],
        )
        return self.store.insert_aggregated_eval_run(
            skill_version_id=skill_version_id,
            eval_set_id=eval_set_id,
            actor=actor,
            environment_tags=list(tags),
            run_context=context,
            run_context_hash=context_hash,
            summary=decision["summary"],
            case_results=decision["case_results"],
        )

    def accept_eval_run_verification(self, *, eval_run_id: str, note: str | None, actor: str) -> Any:
        return self.store.accept_eval_run_verification(eval_run_id=eval_run_id, note=note, actor=actor)
