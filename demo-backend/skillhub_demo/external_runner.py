from __future__ import annotations

import argparse
import json
from typing import Any, Dict, Iterable, List, Set
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .eval_result_import import validate_eval_result_import_shape
from .store import digest


def build_eval_result_payload(
    base_url: str,
    variant_version_id: str,
    eval_set_version_id: str,
    strategy_ref: str,
    fail_case_version_ids: Iterable[str] = (),
    fail_case_title_contains: Iterable[str] = (),
    run_config_hash: str = "",
) -> Dict[str, Any]:
    eval_set = fetch_eval_set(base_url, eval_set_version_id)
    case_refs = eval_set["eval_set_version"]["case_version_refs"]
    if not isinstance(case_refs, list) or not all(isinstance(item, str) for item in case_refs):
        raise ValueError("GET /api/eval-set returned invalid case_version_refs")

    fail_refs: Set[str] = set(fail_case_version_ids)
    fail_refs.update(resolve_case_title_filters(eval_set, fail_case_title_contains))
    unknown = sorted(fail_refs - set(case_refs))
    if unknown:
        raise ValueError("Fail case versions are not in eval set: %s" % ", ".join(unknown))

    config = {
        "mode": "demo-pass-fail",
        "fail_case_version_ids": sorted(fail_refs),
    }
    payload = {
        "variant_version_id": variant_version_id,
        "eval_set_version_id": eval_set_version_id,
        "strategy_ref": strategy_ref,
        "run_config_hash": run_config_hash or digest(json.dumps(config, sort_keys=True)),
        "config": config,
        "results": {case_ref: case_ref not in fail_refs for case_ref in case_refs},
        "metadata": {
            "runner": "skillhub_demo.external_runner",
            "source_eval_set_version": eval_set_version_id,
        },
    }
    validate_eval_result_import_shape(payload)
    return payload


def import_eval_result(base_url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    return post_json(base_url, "/api/eval-result-imports", payload)


def fetch_eval_set(base_url: str, eval_set_version_id: str) -> Dict[str, Any]:
    query = urlencode({"eval_set_version_id": eval_set_version_id})
    return get_json(base_url, "/api/eval-set?%s" % query)


def get_json(base_url: str, path: str) -> Dict[str, Any]:
    with urlopen("%s%s" % (base_url.rstrip("/"), path), timeout=10) as response:
        value = json.loads(response.read().decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Expected JSON object from %s" % path)
    return value


def post_json(base_url: str, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    request = Request(
        "%s%s" % (base_url.rstrip("/"), path),
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=10) as response:
        value = json.loads(response.read().decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Expected JSON object from %s" % path)
    return value


def parse_fail_case_refs(values: List[str]) -> List[str]:
    refs: List[str] = []
    for value in values:
        refs.extend(item.strip() for item in value.split(",") if item.strip())
    return refs


def resolve_case_title_filters(eval_set: Dict[str, Any], filters: Iterable[str]) -> Set[str]:
    refs: Set[str] = set()
    cases = eval_set.get("cases")
    if not isinstance(cases, list):
        raise ValueError("GET /api/eval-set returned invalid cases")

    for raw_filter in filters:
        title_filter = raw_filter.strip()
        if not title_filter:
            continue
        matches = [
            item
            for item in cases
            if isinstance(item, dict)
            and isinstance(item.get("id"), str)
            and isinstance(item.get("title"), str)
            and title_filter in item["title"]
        ]
        if not matches:
            raise ValueError("No eval case title contains: %s" % title_filter)
        refs.update(item["id"] for item in matches)
    return refs


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a minimal external eval import against the SkillHub demo API.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8788")
    parser.add_argument("--variant-version-id", required=True)
    parser.add_argument("--eval-set-version-id", required=True)
    parser.add_argument("--strategy-ref", default="external-demo-runner-v1")
    parser.add_argument("--run-config-hash", default="")
    parser.add_argument(
        "--fail-case-version-id",
        action="append",
        default=[],
        help="Case version id to mark failed. Can be passed multiple times or as comma-separated values.",
    )
    parser.add_argument(
        "--fail-case-title-contains",
        action="append",
        default=[],
        help="Mark matching case versions failed by searching the eval case title returned from GET /api/eval-set.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print payload without importing it.")
    args = parser.parse_args()

    payload = build_eval_result_payload(
        base_url=args.base_url,
        variant_version_id=args.variant_version_id,
        eval_set_version_id=args.eval_set_version_id,
        strategy_ref=args.strategy_ref,
        fail_case_version_ids=parse_fail_case_refs(args.fail_case_version_id),
        fail_case_title_contains=args.fail_case_title_contains,
        run_config_hash=args.run_config_hash,
    )
    if args.dry_run:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    result = import_eval_result(args.base_url, payload)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
