from __future__ import annotations

import json
from dataclasses import replace
from typing import Any

from skillhub.application.in_memory_workspace import InMemoryWorkspace
from skillhub.domain.errors import InvariantError, NotFoundError
from skillhub.domain.models import (
    ArtifactRef,
    CaseResult,
    ContentRef,
    EvalCase,
    EvalCaseVersion,
    EvalRun,
    EvalSet,
    EvalSetVersion,
    Skill,
    SkillVersion,
    digest_text,
    new_id,
    normalize_tags,
    utc_now,
)


class SkillHubService:
    def __init__(self, workspace: InMemoryWorkspace):
        self.workspace = workspace

    def create_skill(
        self,
        *,
        slug: str,
        owner_ref: str,
        content_ref: ContentRef,
        change_summary: str,
        actor: str,
    ) -> Skill:
        now = utc_now()
        skill = Skill(id=new_id("skill"), slug=slug, owner_ref=owner_ref, current_version_id=None, created_at=now)
        self.workspace.skills[skill.id] = skill

        version = self.create_skill_version(
            skill_id=skill.id,
            content_ref=content_ref,
            change_summary=change_summary,
            actor=actor,
            make_current=True,
        )
        eval_set = EvalSet(
            id=new_id("evalset"),
            skill_id=skill.id,
            name="Primary",
            description="Primary regression suite",
            current_version_id=None,
            created_at=now,
        )
        self.workspace.eval_sets[eval_set.id] = eval_set
        eval_set_version = EvalSetVersion(
            id=new_id("evalsetver"),
            eval_set_id=eval_set.id,
            version_number=1,
            case_version_ids=(),
            created_at=now,
        )
        self.workspace.eval_set_versions[eval_set_version.id] = eval_set_version
        self.workspace.eval_sets[eval_set.id] = replace(eval_set, current_version_id=eval_set_version.id)
        return replace(self.workspace.skills[skill.id], current_version_id=version.id)

    def create_skill_version(
        self,
        *,
        skill_id: str,
        content_ref: ContentRef,
        change_summary: str,
        actor: str,
        make_current: bool,
    ) -> SkillVersion:
        skill = self._skill(skill_id)
        version = SkillVersion(
            id=new_id("skillver"),
            skill_id=skill_id,
            version_number=self._next_skill_version_number(skill_id),
            content_ref=content_ref,
            change_summary=change_summary,
            created_at=utc_now(),
            created_by=actor,
        )
        self.workspace.skill_versions[version.id] = version
        if make_current:
            self.workspace.skills[skill_id] = replace(skill, current_version_id=version.id)
        return version

    def create_eval_case(
        self,
        *,
        skill_id: str,
        title: str,
        input_text: str,
        expected_output: str,
        notes: str | None = None,
    ) -> EvalSetVersion:
        self._skill(skill_id)
        eval_set = self._primary_eval_set(skill_id)
        current_set_version = self._eval_set_version(eval_set.current_version_id)
        now = utc_now()
        case = EvalCase(id=new_id("case"), skill_id=skill_id, title=title, current_version_id="", created_at=now)
        case_version = EvalCaseVersion(
            id=new_id("casever"),
            case_id=case.id,
            version_number=1,
            input_ref=self._artifact("eval_input", input_text),
            expected_output_ref=self._artifact("expected_output", expected_output),
            notes=notes,
            created_at=now,
        )
        self.workspace.eval_cases[case.id] = replace(case, current_version_id=case_version.id)
        self.workspace.eval_case_versions[case_version.id] = case_version

        return self._update_current_eval_set_cases(
            skill_id=skill_id,
            case_version_ids=(*current_set_version.case_version_ids, case_version.id),
        )

    def create_eval_case_version(
        self,
        *,
        case_id: str,
        input_text: str,
        expected_output: str,
        notes: str | None = None,
        make_current: bool = True,
    ) -> EvalCaseVersion:
        case = self._eval_case(case_id)
        version = EvalCaseVersion(
            id=new_id("casever"),
            case_id=case_id,
            version_number=self._next_case_version_number(case_id),
            input_ref=self._artifact("eval_input", input_text),
            expected_output_ref=self._artifact("expected_output", expected_output),
            notes=notes,
            created_at=utc_now(),
        )
        self.workspace.eval_case_versions[version.id] = version
        if make_current:
            self.workspace.eval_cases[case_id] = replace(case, current_version_id=version.id)
            self._append_eval_set_version_with_case_replacement(case.skill_id, case_id, version.id)
        return version

    def record_eval_run(
        self,
        *,
        skill_version_id: str,
        eval_set_version_id: str,
        strategy: str,
        results: dict[str, bool],
        actor: str,
        environment_tags: list[str] | None = None,
        run_context: dict[str, Any] | None = None,
    ) -> EvalRun:
        skill_version = self._skill_version(skill_version_id)
        eval_set_version = self._eval_set_version(eval_set_version_id)
        eval_set = self._eval_set(eval_set_version.eval_set_id)
        if eval_set.skill_id != skill_version.skill_id:
            raise InvariantError("EvalRun must bind a skill version and eval set version from the same skill.")

        tags = normalize_tags(environment_tags or [])
        context = self._canonical_json(run_context or {})
        run = EvalRun(
            id=new_id("evalrun"),
            skill_version_id=skill_version_id,
            eval_set_version_id=eval_set_version_id,
            strategy=strategy,
            status="finished",
            created_at=utc_now(),
            created_by=actor,
            environment_tags=tags,
            run_context=context,
            run_context_hash=self._run_context_hash(tags, context),
        )
        self.workspace.eval_runs[run.id] = run
        for case_version_id in eval_set_version.case_version_ids:
            passed = bool(results.get(case_version_id, False))
            self.workspace.case_results.append(
                CaseResult(run_id=run.id, case_version_id=case_version_id, passed=passed, score=1 if passed else 0)
            )
        return run

    def _append_eval_set_version_with_case_replacement(
        self,
        skill_id: str,
        case_id: str,
        case_version_id: str,
    ) -> EvalSetVersion:
        eval_set = self._primary_eval_set(skill_id)
        current_set_version = self._eval_set_version(eval_set.current_version_id)
        next_case_version_ids = tuple(
            case_version_id if self._eval_case_version(item).case_id == case_id else item
            for item in current_set_version.case_version_ids
        )
        return self._update_current_eval_set_cases(skill_id=skill_id, case_version_ids=next_case_version_ids)

    def _update_current_eval_set_cases(self, skill_id: str, case_version_ids: tuple[str, ...]) -> EvalSetVersion:
        eval_set = self._primary_eval_set(skill_id)
        current_set_version = self._eval_set_version(eval_set.current_version_id)
        if any(run.eval_set_version_id == current_set_version.id for run in self.workspace.eval_runs.values()):
            next_set_version = EvalSetVersion(
                id=new_id("evalsetver"),
                eval_set_id=eval_set.id,
                version_number=current_set_version.version_number + 1,
                case_version_ids=case_version_ids,
                created_at=utc_now(),
            )
            self.workspace.eval_set_versions[next_set_version.id] = next_set_version
            self.workspace.eval_sets[eval_set.id] = replace(eval_set, current_version_id=next_set_version.id)
            return next_set_version
        updated_set_version = replace(current_set_version, case_version_ids=case_version_ids)
        self.workspace.eval_set_versions[current_set_version.id] = updated_set_version
        self.workspace.eval_sets[eval_set.id] = replace(eval_set, current_version_id=current_set_version.id)
        return updated_set_version

    def _artifact(self, kind: str, content: str) -> ArtifactRef:
        digest = digest_text(content)
        return ArtifactRef(
            id=new_id("artifact"),
            kind=kind,
            locator=f"memory:{digest}",
            digest=digest,
            media_type="text/plain",
        )

    def _next_skill_version_number(self, skill_id: str) -> int:
        return 1 + max(
            (item.version_number for item in self.workspace.skill_versions.values() if item.skill_id == skill_id),
            default=0,
        )

    def _next_case_version_number(self, case_id: str) -> int:
        return 1 + max(
            (item.version_number for item in self.workspace.eval_case_versions.values() if item.case_id == case_id),
            default=0,
        )

    def _skill(self, skill_id: str) -> Skill:
        try:
            return self.workspace.skills[skill_id]
        except KeyError as exc:
            raise NotFoundError(f"Skill not found: {skill_id}") from exc

    def _skill_version(self, version_id: str | None) -> SkillVersion:
        if version_id is None:
            raise NotFoundError("Skill has no current version.")
        try:
            return self.workspace.skill_versions[version_id]
        except KeyError as exc:
            raise NotFoundError(f"SkillVersion not found: {version_id}") from exc

    def _eval_set(self, eval_set_id: str) -> EvalSet:
        try:
            return self.workspace.eval_sets[eval_set_id]
        except KeyError as exc:
            raise NotFoundError(f"EvalSet not found: {eval_set_id}") from exc

    def _eval_set_version(self, version_id: str | None) -> EvalSetVersion:
        if version_id is None:
            raise NotFoundError("EvalSet has no current version.")
        try:
            return self.workspace.eval_set_versions[version_id]
        except KeyError as exc:
            raise NotFoundError(f"EvalSetVersion not found: {version_id}") from exc

    def _eval_case(self, case_id: str) -> EvalCase:
        try:
            return self.workspace.eval_cases[case_id]
        except KeyError as exc:
            raise NotFoundError(f"EvalCase not found: {case_id}") from exc

    def _eval_case_version(self, case_version_id: str) -> EvalCaseVersion:
        try:
            return self.workspace.eval_case_versions[case_version_id]
        except KeyError as exc:
            raise NotFoundError(f"EvalCaseVersion not found: {case_version_id}") from exc

    def _primary_eval_set(self, skill_id: str) -> EvalSet:
        for eval_set in self.workspace.eval_sets.values():
            if eval_set.skill_id == skill_id:
                return eval_set
        raise NotFoundError(f"Primary EvalSet not found for skill: {skill_id}")

    def _canonical_json(self, value: dict[str, Any]) -> dict[str, Any]:
        return json.loads(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")))

    def _run_context_hash(self, tags: tuple[str, ...], context: dict[str, Any]) -> str:
        payload = {"environment_tags": list(tags), "run_context": context}
        return digest_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
