from __future__ import annotations

from dataclasses import dataclass, field, replace

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
    TagSet,
    Variant,
    VariantVersion,
    digest_text,
    new_id,
    normalize_tags,
    utc_now,
)


@dataclass
class InMemoryWorkspace:
    skills: dict[str, Skill] = field(default_factory=dict)
    tag_sets: dict[str, TagSet] = field(default_factory=dict)
    variants: dict[str, Variant] = field(default_factory=dict)
    variant_versions: dict[str, VariantVersion] = field(default_factory=dict)
    eval_sets: dict[str, EvalSet] = field(default_factory=dict)
    eval_set_versions: dict[str, EvalSetVersion] = field(default_factory=dict)
    eval_cases: dict[str, EvalCase] = field(default_factory=dict)
    eval_case_versions: dict[str, EvalCaseVersion] = field(default_factory=dict)
    eval_runs: dict[str, EvalRun] = field(default_factory=dict)
    case_results: list[CaseResult] = field(default_factory=list)


class SkillHubService:
    def __init__(self, workspace: InMemoryWorkspace):
        self.workspace = workspace

    def create_skill(
        self,
        *,
        slug: str,
        owner_ref: str,
        variant_name: str,
        variant_label: str,
        variant_summary: str,
        tags: list[str],
        content_ref: ContentRef,
        change_summary: str,
        actor: str,
    ) -> Skill:
        now = utc_now()
        skill = Skill(
            id=new_id("skill"),
            slug=slug,
            owner_ref=owner_ref,
            default_variant_id=None,
            created_at=now,
        )
        self.workspace.skills[skill.id] = skill

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

        variant = self.create_variant(
            skill_id=skill.id,
            name=variant_name,
            label=variant_label,
            summary=variant_summary,
            tags=tags,
            content_ref=content_ref,
            change_summary=change_summary,
            actor=actor,
        )
        self.workspace.skills[skill.id] = replace(skill, default_variant_id=variant.id)
        return self.workspace.skills[skill.id]

    def create_variant(
        self,
        *,
        skill_id: str,
        name: str,
        label: str,
        summary: str,
        tags: list[str],
        content_ref: ContentRef,
        change_summary: str,
        actor: str,
    ) -> Variant:
        self._skill(skill_id)
        now = utc_now()
        tag_set = self._get_or_create_tag_set(tags)
        variant = Variant(
            id=new_id("variant"),
            skill_id=skill_id,
            name=name,
            label=label,
            summary=summary,
            tag_set_id=tag_set.id,
            current_version_id=None,
            created_at=now,
        )
        self.workspace.variants[variant.id] = variant
        version = self.create_variant_version(
            variant_id=variant.id,
            content_ref=content_ref,
            change_summary=change_summary,
            actor=actor,
            make_current=True,
        )
        return self.workspace.variants[version.variant_id]

    def create_variant_version(
        self,
        *,
        variant_id: str,
        content_ref: ContentRef,
        change_summary: str,
        actor: str,
        make_current: bool,
    ) -> VariantVersion:
        variant = self._variant(variant_id)
        version = VariantVersion(
            id=new_id("varver"),
            variant_id=variant_id,
            version_number=self._next_variant_version_number(variant_id),
            content_ref=content_ref,
            change_summary=change_summary,
            created_at=utc_now(),
            created_by=actor,
        )
        self.workspace.variant_versions[version.id] = version
        if make_current:
            self.workspace.variants[variant_id] = replace(variant, current_version_id=version.id)
        return version

    def promote_variant_version(self, *, variant_id: str, version_id: str) -> Variant:
        variant = self._variant(variant_id)
        version = self._variant_version(version_id)
        if version.variant_id != variant_id:
            raise InvariantError("Variant current_version_id must point to its own version.")
        promoted = replace(variant, current_version_id=version_id)
        self.workspace.variants[variant_id] = promoted
        return promoted

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
        case = EvalCase(
            id=new_id("case"),
            skill_id=skill_id,
            title=title,
            current_version_id="",
            created_at=now,
        )
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

        next_set_version = EvalSetVersion(
            id=new_id("evalsetver"),
            eval_set_id=eval_set.id,
            version_number=current_set_version.version_number + 1,
            case_version_ids=(*current_set_version.case_version_ids, case_version.id),
            created_at=now,
        )
        self.workspace.eval_set_versions[next_set_version.id] = next_set_version
        self.workspace.eval_sets[eval_set.id] = replace(eval_set, current_version_id=next_set_version.id)
        return next_set_version

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
        variant_version_id: str,
        eval_set_version_id: str,
        strategy: str,
        results: dict[str, bool],
        actor: str,
    ) -> EvalRun:
        variant_version = self._variant_version(variant_version_id)
        variant = self._variant(variant_version.variant_id)
        eval_set_version = self._eval_set_version(eval_set_version_id)
        eval_set = self._eval_set(eval_set_version.eval_set_id)
        if eval_set.skill_id != variant.skill_id:
            raise InvariantError("EvalRun must bind a variant version and eval set version from the same skill.")

        run = EvalRun(
            id=new_id("evalrun"),
            variant_version_id=variant_version_id,
            eval_set_version_id=eval_set_version_id,
            strategy=strategy,
            status="finished",
            created_at=utc_now(),
            created_by=actor,
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
        next_set_version = EvalSetVersion(
            id=new_id("evalsetver"),
            eval_set_id=eval_set.id,
            version_number=current_set_version.version_number + 1,
            case_version_ids=next_case_version_ids,
            created_at=utc_now(),
        )
        self.workspace.eval_set_versions[next_set_version.id] = next_set_version
        self.workspace.eval_sets[eval_set.id] = replace(eval_set, current_version_id=next_set_version.id)
        return next_set_version

    def _get_or_create_tag_set(self, tags: list[str]) -> TagSet:
        normalized = normalize_tags(tags)
        normalized_hash = digest_text("\n".join(normalized))
        for tag_set in self.workspace.tag_sets.values():
            if tag_set.normalized_hash == normalized_hash:
                return tag_set
        tag_set = TagSet(id=new_id("tagset"), tags=normalized, normalized_hash=normalized_hash)
        self.workspace.tag_sets[tag_set.id] = tag_set
        return tag_set

    def _artifact(self, kind: str, content: str) -> ArtifactRef:
        digest = digest_text(content)
        return ArtifactRef(
            id=new_id("artifact"),
            kind=kind,
            locator=f"memory:{digest}",
            digest=digest,
            media_type="text/plain",
        )

    def _next_variant_version_number(self, variant_id: str) -> int:
        return 1 + max(
            (item.version_number for item in self.workspace.variant_versions.values() if item.variant_id == variant_id),
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

    def _variant(self, variant_id: str) -> Variant:
        try:
            return self.workspace.variants[variant_id]
        except KeyError as exc:
            raise NotFoundError(f"Variant not found: {variant_id}") from exc

    def _variant_version(self, version_id: str | None) -> VariantVersion:
        if version_id is None:
            raise NotFoundError("Variant has no current version.")
        try:
            return self.workspace.variant_versions[version_id]
        except KeyError as exc:
            raise NotFoundError(f"VariantVersion not found: {version_id}") from exc

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
