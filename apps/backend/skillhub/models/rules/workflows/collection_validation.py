from __future__ import annotations

from typing import Any

from .config_validation import validate_config_spec
from .log_sql import validate_log_query
from .validation_helpers import append_duplicates, append_legacy_schema_warnings, append_missing_titles, append_optional_duplicates, issue


def validate_collection_identity(definitions: list[dict[str, Any]], issues: list[dict[str, Any]]) -> None:
    references = [{"reference": f"{item['id']}@{item['revision']}"} for item in definitions]
    append_optional_duplicates(references, "reference", "DUPLICATE_COLLECTION_REFERENCE", "Collection 引用", issues, {"type": "collections"})
    for definition in definitions:
        selection = {"type": "collection", "id": definition["id"], "revision": definition["revision"]}
        if not definition["metadata"]["name"].strip():
            issues.append(issue("MISSING_COLLECTION_NAME", "error", "采集名称不能为空。", {**selection, "field": "metadata.name"}))
        _validate_spec(definition, issues, selection)
        append_duplicates(definition["inputs"], "id", "MISSING_COLLECTION_INPUT_ID", "DUPLICATE_COLLECTION_INPUT_ID", "Collection 输入 ID", issues, selection)
        append_duplicates(definition["inputs"], "key", "MISSING_COLLECTION_INPUT_KEY", "DUPLICATE_COLLECTION_INPUT_KEY", "Collection 输入 key", issues, selection)
        append_missing_titles(definition["inputs"], "Collection 输入名称", issues, selection)
        append_legacy_schema_warnings([*definition["inputs"], *definition["outputs"]], issues, selection)
        append_duplicates(definition["outputs"], "id", "MISSING_COLLECTION_OUTPUT_ID", "DUPLICATE_COLLECTION_OUTPUT_ID", "Collection 输出 ID", issues, selection)
        append_duplicates(definition["outputs"], "key", "MISSING_COLLECTION_OUTPUT_KEY", "DUPLICATE_COLLECTION_OUTPUT_KEY", "Collection 输出 key", issues, selection)


def _validate_spec(definition: dict[str, Any], issues: list[dict[str, Any]], selection: dict[str, Any]) -> None:
    spec = definition["spec"]
    if spec["collectionType"] == "cli":
        _validate_cli_spec(spec, definition, issues, selection)
        return
    if spec["collectionType"] == "config":
        validate_config_spec(spec, selection, issues)
        return
    _validate_log_spec(spec, definition, issues, selection)


def _validate_cli_spec(spec, definition, issues, selection) -> None:
    command = spec["commandTemplate"]
    if not command.strip():
        label = definition["metadata"]["name"] or definition["key"]
        issues.append(issue("MISSING_COLLECTION_COMMAND", "error", f"采集“{label}”的采集命令不能为空。", {**selection, "field": "spec.commandTemplate"}))
    elif "\n" in command or "\r" in command:
        issues.append(issue("MULTILINE_COLLECTION_COMMAND", "error", "采集命令必须为单行。", {**selection, "field": "spec.commandTemplate"}))
    append_duplicates(spec["outputSamples"], "id", "MISSING_COLLECTION_SAMPLE_ID", "DUPLICATE_COLLECTION_SAMPLE_ID", "回显示例 ID", issues, selection)


def _validate_log_spec(spec, definition, issues, selection) -> None:
    queries = spec["queries"]
    _validate_log_item_ids(queries, "spec.queries", "日志聚合查询", "MISSING_LOG_QUERY_ID", "DUPLICATE_LOG_QUERY_ID", issues, selection)

    scalar_types = {"string", "integer", "number", "boolean"}
    outputs = {item["id"]: item for item in definition["outputs"]}
    assigned: dict[str, str] = {}
    input_keys = [item["key"] for item in definition["inputs"]]
    unresolved_references: list[tuple[dict[str, Any], str]] = []
    for query in queries:
        query_path = f"spec.queries.{query['id'] or '_'}"
        base = {**selection, "itemId": query["id"]}
        output_ids = query["outputIds"]
        if not output_ids:
            issues.append(
                issue(
                    "LOG_QUERY_OUTPUT_NOT_ASSIGNED",
                    "error",
                    "日志聚合查询至少需要一个输出字段。",
                    {**base, "field": f"{query_path}.outputIds"},
                )
            )
        expected_keys: list[str] = []
        for output_id in output_ids:
            output = outputs.get(output_id)
            if output is None:
                unresolved_references.append((base, query_path))
                continue
            if output_id in assigned:
                issues.append(
                    issue(
                        "LOG_QUERY_OUTPUT_NOT_UNIQUE",
                        "error",
                        "一个输出字段只能归属一条日志聚合查询。",
                        {**base, "field": f"{query_path}.outputIds"},
                    )
                )
            else:
                assigned[output_id] = query["id"]
            expected_keys.append(output["key"])
        for diagnostic in validate_log_query(query["sql"], expected_keys, input_keys):
            issues.append(issue(diagnostic.code, "error", diagnostic.message, {**base, "field": f"{query_path}.sql"}))
    for output_id, output in outputs.items():
        if output["schema"].get("type") not in scalar_types:
            issues.append(
                issue(
                    "LOG_OUTPUT_SCHEMA_NOT_SCALAR",
                    "error",
                    "日志聚合输出只支持四种标量 Schema。",
                    {**selection, "itemId": output_id, "field": f"outputs.{output_id}.schema"},
                )
            )
        if output_id not in assigned:
            issues.append(
                issue(
                    "LOG_QUERY_OUTPUT_NOT_ASSIGNED",
                    "error",
                    "日志聚合输出必须归属一条查询。",
                    {**selection, "itemId": output_id, "field": f"outputs.{output_id}"},
                )
            )
    for parameter in definition["inputs"]:
        if parameter["schema"].get("type") not in scalar_types:
            issues.append(
                issue(
                    "LOG_INPUT_SCHEMA_NOT_SCALAR",
                    "error",
                    "日志聚合输入只支持四种标量 Schema。",
                    {**selection, "itemId": parameter["id"], "field": f"inputs.{parameter['id']}.schema"},
                )
            )
    for base, query_path in unresolved_references:
        issues.append(
            issue(
                "LOG_QUERY_OUTPUT_NOT_ASSIGNED",
                "error",
                "日志聚合查询引用了不存在的输出字段。",
                {**base, "field": f"{query_path}.outputIds"},
            )
        )
    _validate_log_item_ids(
        spec["outputSamples"],
        "spec.outputSamples",
        "日志样例",
        "MISSING_COLLECTION_SAMPLE_ID",
        "DUPLICATE_COLLECTION_SAMPLE_ID",
        issues,
        selection,
    )


def _validate_log_item_ids(items, path, label, missing_code, duplicate_code, issues, selection) -> None:
    seen: set[str] = set()
    for item in items:
        item_id = item["id"]
        normalized = item_id.strip()
        item_path = f"{path}.{item_id or '_'}"
        item_selection = {**selection, "itemId": item_id, "field": f"{item_path}.id"}
        if not normalized:
            issues.append(issue(missing_code, "error", f"{label} ID 不能为空。", item_selection))
        elif normalized in seen:
            issues.append(issue(duplicate_code, "error", f"{label} ID“{item_id}”重复。", item_selection))
        seen.add(normalized)


__all__ = ["validate_collection_identity"]
