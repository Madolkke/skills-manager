from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CreateSkillResult:
    skill_id: str
    skill_version_id: str
    eval_set_id: str
    version_number: int
    version: str


@dataclass(frozen=True)
class CreateSkillVersionResult:
    skill_id: str
    skill_version_id: str
    version_number: int
    version: str


@dataclass(frozen=True)
class CreateEvalCaseResult:
    skill_id: str
    eval_set_id: str
    eval_case_id: str
    eval_case_version_id: str
    input_artifact_id: str
    expected_output_artifact_id: str
    attachment_artifact_id: str | None = None


@dataclass(frozen=True)
class CreatedEvalCaseResult:
    eval_case_id: str
    eval_case_version_id: str
    input_artifact_id: str
    expected_output_artifact_id: str
    attachment_artifact_id: str | None = None


@dataclass(frozen=True)
class CreateEvalCasesBatchResult:
    skill_id: str
    eval_set_id: str
    created: tuple[CreatedEvalCaseResult, ...]


@dataclass(frozen=True)
class RecordEvalRunResult:
    eval_run_id: str
    skill_id: str
    skill_version_id: str
    eval_set_id: str
    passed: int
    failed: int
    total: int
    environment_tags: tuple[str, ...]
    run_context: dict[str, Any]
    run_context_hash: str


@dataclass(frozen=True)
class RecordEvalCaseRunResult:
    eval_case_run_id: str
    job_id: str
    skill_id: str
    skill_version_id: str
    eval_set_id: str
    case_version_id: str
    status: str
    run_context_hash: str
    passed: bool | None = None
    score: int | None = None


@dataclass(frozen=True)
class EvalSetDetail:
    eval_set: dict[str, Any]
    cases: list[dict[str, Any]]


@dataclass(frozen=True)
class EvalRunDetail:
    eval_run: dict[str, Any]
    skill: dict[str, Any]
    skill_version: dict[str, Any]
    eval_set: dict[str, Any]
    case_results: list[dict[str, Any]]


@dataclass(frozen=True)
class EvalCaseRunDetail:
    eval_case_run: dict[str, Any]
    skill: dict[str, Any]
    skill_version: dict[str, Any]
    eval_set: dict[str, Any]
    case: dict[str, Any]
    case_version: dict[str, Any]
