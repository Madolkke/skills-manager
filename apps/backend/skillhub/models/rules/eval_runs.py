from __future__ import annotations

import json
from typing import Any

from skillhub.models.errors import FieldError, FieldInvariantError, InvariantError
from skillhub.models.entities import digest_text, normalize_tags


def canonical_run_context(value: dict[str, Any] | None) -> dict[str, Any]:
    try:
        return json.loads(json.dumps(value or {}, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    except (TypeError, ValueError) as exc:
        raise InvariantError("Run context must be JSON serializable.") from exc


def normalize_run_environment(
    environment_tags: list[str] | tuple[str, ...] | None,
    run_context: dict[str, Any] | None,
) -> tuple[tuple[str, ...], dict[str, Any], str]:
    tags = normalize_tags(list(environment_tags or []))
    context = canonical_run_context(run_context)
    return tags, context, run_context_hash(tags, context)


def run_context_hash(tags: tuple[str, ...], context: dict[str, Any]) -> str:
    payload = {"environment_tags": list(tags), "run_context": context}
    return digest_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


def decide_eval_run_aggregation(
    *,
    case_version_ids: list[str],
    latest_case_runs: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    if not case_version_ids:
        raise FieldInvariantError(
            "EvalRun aggregation requires at least one case.",
            [
                FieldError(
                    field="eval_set_id",
                    message="当前测评集没有测试例，无法生成测评记录。",
                    code="eval_run.eval_set_empty",
                )
            ],
        )
    missing = [case_version_id for case_version_id in case_version_ids if case_version_id not in latest_case_runs]
    if missing:
        raise FieldInvariantError(
            "EvalRun aggregation requires finished case runs.",
            [
                FieldError(field=f"case_runs.{case_version_id}", message="该 case 尚未完成测评。", code="eval_run.case_run_missing")
                for case_version_id in missing
            ],
        )
    passed_count = sum(1 for case_version_id in case_version_ids if latest_case_runs[case_version_id]["passed"])
    failed_count = len(case_version_ids) - passed_count
    return {
        "passed": passed_count,
        "failed": failed_count,
        "total": len(case_version_ids),
        "summary": {"passed": passed_count, "failed": failed_count, "total": len(case_version_ids)},
        "case_results": [
            {
                "case_version_id": case_version_id,
                "passed": latest_case_runs[case_version_id]["passed"],
                "score": latest_case_runs[case_version_id]["score"],
                "result_artifact_id": latest_case_runs[case_version_id]["result_artifact_id"],
            }
            for case_version_id in case_version_ids
        ],
    }
