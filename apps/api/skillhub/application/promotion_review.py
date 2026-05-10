from __future__ import annotations

from typing import Any


COMPARISON_KEYS = (
    "fixed",
    "regressed",
    "stable_pass",
    "stable_fail",
    "missing_baseline",
    "missing_candidate",
)

CHANGE_LABELS = {
    "fixed": "修复",
    "regressed": "回退",
    "stable_pass": "稳定通过",
    "stable_fail": "仍未通过",
    "missing_baseline": "缺少对照",
    "missing_candidate": "候选缺失",
}


def promotion_change(*, current_passed: bool | None, candidate_passed: bool | None) -> str:
    if candidate_passed is None:
        return "missing_candidate"
    if current_passed is None:
        return "missing_baseline"
    if not current_passed and candidate_passed:
        return "fixed"
    if current_passed and not candidate_passed:
        return "regressed"
    if current_passed and candidate_passed:
        return "stable_pass"
    return "stable_fail"


def build_promotion_case_comparisons(
    *,
    eval_set_cases: list[dict[str, Any]],
    current_results: dict[str, bool] | None,
    candidate_results: dict[str, bool] | None,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    summary = {key: 0 for key in COMPARISON_KEYS}
    comparisons = []
    for case_entry in eval_set_cases:
        case_version = case_entry["case_version"]
        case_version_id = case_version["id"]
        current_passed = current_results.get(case_version_id) if current_results is not None else None
        candidate_passed = candidate_results.get(case_version_id) if candidate_results is not None else None
        change = promotion_change(current_passed=current_passed, candidate_passed=candidate_passed)
        summary[change] += 1
        comparisons.append(
            {
                "case_id": case_entry["case"]["id"],
                "case_title": case_entry["case"]["title"],
                "case_version_id": case_version_id,
                "change": change,
                "change_label": CHANGE_LABELS[change],
                "current_passed": current_passed,
                "candidate_passed": candidate_passed,
                "input_text": case_version["input_artifact"].get("content_text"),
                "expected_output_text": case_version["expected_output_artifact"].get("content_text"),
            }
        )
    return comparisons, summary


def build_promotion_readiness(
    *,
    candidate_run_present: bool,
    candidate_result_count: int,
    case_count: int,
    comparison_summary: dict[str, int],
    case_comparisons: list[dict[str, Any]],
    blocking_items: list[str],
    eval_set_version_number: int,
) -> dict[str, Any]:
    passing_items = [
        "测评绑定的是 exact VariantVersion + EvalSetVersion",
        f"目标测试集版本为 {eval_set_version_number}",
    ]
    if not candidate_run_present:
        return {
            "status": "unverified",
            "label": "未验证",
            "reason": "候选版本没有在目标测试集版本上完成测评",
            "requires_note": False,
            "risk_items": [],
            "blocking_items": [],
            "passing_items": passing_items,
        }

    next_blocking_items = list(blocking_items)
    if candidate_result_count < case_count:
        next_blocking_items.append("候选版本测评不完整")
    if next_blocking_items:
        return {
            "status": "blocked",
            "label": "无法设为当前版本",
            "reason": next_blocking_items[0],
            "requires_note": False,
            "risk_items": [],
            "blocking_items": next_blocking_items,
            "passing_items": passing_items,
        }

    risk_items = []
    if comparison_summary["regressed"] > 0:
        risk_items.append(f"发现 {comparison_summary['regressed']} 个回退")
    if comparison_summary["stable_fail"] > 0:
        risk_items.append(f"仍有 {comparison_summary['stable_fail']} 个仍未通过的用例")
    if comparison_summary["missing_baseline"] > 0:
        risk_items.append("缺少当前版本对照测评")
    candidate_failed_count = sum(1 for item in case_comparisons if item["candidate_passed"] is False)
    requires_note = comparison_summary["regressed"] > 0 or comparison_summary["stable_fail"] > 0 or candidate_failed_count > 0
    passing_items.append("候选版本在目标测试集版本上跑过完整测评")

    if risk_items:
        return {
            "status": "risky",
            "label": "有风险",
            "reason": risk_items[0],
            "requires_note": requires_note,
            "risk_items": risk_items,
            "blocking_items": [],
            "passing_items": passing_items,
        }
    return {
        "status": "ready",
        "label": "可设为当前版本",
        "reason": "候选版本已验证，且没有发现回退",
        "requires_note": False,
        "risk_items": [],
        "blocking_items": [],
        "passing_items": passing_items,
    }
