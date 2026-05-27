from __future__ import annotations

from dataclasses import dataclass, field

from skillhub.domain.models import CaseResult, EvalCase, EvalCaseVersion, EvalRun, EvalSet, EvalSetVersion, Skill, SkillVersion


@dataclass
class InMemoryWorkspace:
    skills: dict[str, Skill] = field(default_factory=dict)
    skill_versions: dict[str, SkillVersion] = field(default_factory=dict)
    eval_sets: dict[str, EvalSet] = field(default_factory=dict)
    eval_set_versions: dict[str, EvalSetVersion] = field(default_factory=dict)
    eval_cases: dict[str, EvalCase] = field(default_factory=dict)
    eval_case_versions: dict[str, EvalCaseVersion] = field(default_factory=dict)
    eval_runs: dict[str, EvalRun] = field(default_factory=dict)
    case_results: list[CaseResult] = field(default_factory=list)
