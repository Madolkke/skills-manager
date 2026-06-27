from __future__ import annotations

import pytest

from skillhub.models.errors import FieldInvariantError
from skillhub.models.rules.eval_runs import decide_eval_run_aggregation


def test_eval_run_aggregation_policy_builds_summary_and_case_results() -> None:
    decision = decide_eval_run_aggregation(
        case_version_ids=["casever_1", "casever_2"],
        latest_case_runs={
            "casever_1": {"passed": True, "score": 1, "result_artifact_id": "artifact_1"},
            "casever_2": {"passed": False, "score": 0, "result_artifact_id": None},
        },
    )

    assert decision["summary"] == {"passed": 1, "failed": 1, "total": 2}
    assert decision["case_results"] == [
        {"case_version_id": "casever_1", "passed": True, "score": 1, "result_artifact_id": "artifact_1"},
        {"case_version_id": "casever_2", "passed": False, "score": 0, "result_artifact_id": None},
    ]


def test_eval_run_aggregation_policy_rejects_empty_eval_set() -> None:
    with pytest.raises(FieldInvariantError) as exc_info:
        decide_eval_run_aggregation(case_version_ids=[], latest_case_runs={})

    assert exc_info.value.field_errors[0].code == "eval_run.eval_set_empty"


def test_eval_run_aggregation_policy_rejects_missing_case_runs() -> None:
    with pytest.raises(FieldInvariantError) as exc_info:
        decide_eval_run_aggregation(
            case_version_ids=["casever_1", "casever_2"],
            latest_case_runs={"casever_1": {"passed": True, "score": 1, "result_artifact_id": None}},
        )

    assert exc_info.value.field_errors[0].field == "case_runs.casever_2"
    assert exc_info.value.field_errors[0].code == "eval_run.case_run_missing"
