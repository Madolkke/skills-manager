from __future__ import annotations

from typing import Any, Mapping, Sequence


def build_eval_run_matrix(
    *,
    skill: dict[str, Any],
    runs: list[dict[str, Any]],
    eval_set_cases_by_run: Mapping[str, Sequence[dict[str, Any]]],
    results_by_run: Mapping[str, Sequence[dict[str, Any]]],
) -> dict[str, Any]:
    case_rows: dict[str, dict[str, Any]] = {}
    cells = []

    for run in runs:
        run_id = run["eval_run"]["id"]
        results_by_case_version = {result["case_version_id"]: result for result in results_by_run.get(run_id, [])}
        for eval_set_case in eval_set_cases_by_run.get(run_id, []):
            eval_case = eval_set_case["case"]
            case_version = eval_set_case["case_version"]
            case_row = case_rows.setdefault(eval_case["id"], {"case": eval_case, "versions": []})
            if not any(version["case_version_id"] == case_version["id"] for version in case_row["versions"]):
                case_row["versions"].append(
                    {
                        "case_version_id": case_version["id"],
                        "version_number": case_version["version_number"],
                    }
                )
            result = results_by_case_version.get(case_version["id"])
            if result:
                cells.append(
                    {
                        "run_id": run_id,
                        "case_id": eval_case["id"],
                        "case_version_id": case_version["id"],
                        "passed": result["passed"],
                        "score": result["score"],
                    }
                )

    return {
        "skill": skill,
        "runs": runs,
        "cases": list(case_rows.values()),
        "cells": cells,
    }
