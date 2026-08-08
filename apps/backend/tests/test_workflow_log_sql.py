from __future__ import annotations

from copy import deepcopy

import pytest

from skillhub.models.errors import InvariantError
from skillhub.models.rules.workflows import (
    migrate_collection_definition,
    normalize_collection_definition,
    normalize_workflow_document,
    normalize_workflow_import_bundle,
    validate_workflow_document,
    workflow_log_schema_catalog,
)
from skillhub.models.rules.workflows.log_sql import validate_log_query


def test_log_collection_is_a_strict_discriminated_schema():
    definition = normalize_collection_definition(_log_definition())

    assert definition["spec"] == {
        "collectionType": "log",
        "sqlDialect": "duckdb",
        "queries": [{"id": "query-count", "name": "错误计数", "sql": "SELECT count(*) AS error_count FROM logs", "outputIds": ["output-count"]}],
        "outputSamples": [{"id": "sample-1", "name": "空窗", "text": "raw log"}],
    }
    invalid = deepcopy(_log_definition())
    invalid["spec"]["commandTemplate"] = "show version"
    with pytest.raises(InvariantError, match="Extra inputs are not permitted"):
        normalize_collection_definition(invalid)

    missing_dialect = deepcopy(_log_definition())
    del missing_dialect["spec"]["sqlDialect"]
    with pytest.raises(InvariantError, match="sqlDialect"):
        normalize_collection_definition(missing_dialect)


def test_v4_cli_shape_without_discriminator_remains_readable():
    legacy = {
        "id": "collection-cli",
        "revision": 1,
        "key": "cli",
        "metadata": {"name": "命令"},
        "spec": {"commandTemplate": "show version", "outputSamples": []},
        "inputs": [],
        "outputs": [],
    }

    normalized = normalize_collection_definition(legacy)

    assert normalized["spec"]["collectionType"] == "cli"
    document = normalize_workflow_document(
        {
            "documentType": "workflow_bundle",
            "workflow": {"id": "workflow-cli", "revision": 1, "metadata": {"name": "命令", "description": ""}, "inputs": [], "deviceRoles": [], "nodes": []},
            "collectionSnapshots": [legacy],
        }
    )
    assert document["collectionSnapshots"][0]["spec"]["collectionType"] == "cli"


def test_v4_log_migration_explicitly_fills_dialect_but_v5_normalization_does_not() -> None:
    legacy = _log_definition()
    del legacy["spec"]["sqlDialect"]
    with pytest.raises(InvariantError, match="sqlDialect"):
        normalize_collection_definition(legacy)

    migrated = migrate_collection_definition(4, legacy)
    assert migrated["spec"]["collectionType"] == "log"
    assert migrated["spec"]["sqlDialect"] == "duckdb"


def test_legacy_import_log_spec_gets_explicit_dialect_before_strict_parse() -> None:
    bundle = normalize_workflow_import_bundle({
        "documentType": "workflow_import_bundle",
        "workflow": {"metadata": {"name": "日志", "description": ""}, "inputs": [], "deviceRoles": [], "nodes": []},
        "collections": [{
            "localId": "log",
            "key": "log",
            "metadata": {"name": "日志"},
            "spec": {"collectionType": "log", "queries": [], "outputSamples": []},
            "inputs": [],
            "outputs": [],
        }],
    })
    assert bundle["collections"][0]["spec"]["sqlDialect"] == "duckdb"


def test_fixed_log_schema_catalog_is_stable_and_detached():
    catalog = workflow_log_schema_catalog()
    assert catalog == {
        "document_schema_version": 5,
        "dialect": "duckdb",
        "logs_table": "logs",
        "params_table": "params",
        "columns": [
            {"name": "event_time", "duckdb_type": "TIMESTAMP", "nullable": True, "title": "时间", "description": "日志事件时间（无时区）"},
            {"name": "device", "duckdb_type": "VARCHAR", "nullable": True, "title": "设备", "description": "日志来源设备"},
            {"name": "module", "duckdb_type": "VARCHAR", "nullable": True, "title": "模块", "description": "产生日志的模块"},
            {"name": "severity", "duckdb_type": "VARCHAR", "nullable": True, "title": "严重等级", "description": "日志严重等级"},
            {"name": "brief", "duckdb_type": "VARCHAR", "nullable": True, "title": "简述", "description": "日志摘要"},
            {"name": "body", "duckdb_type": "VARCHAR", "nullable": True, "title": "日志体", "description": "原始日志正文"},
        ],
    }
    catalog["columns"][0]["name"] = "changed"
    assert workflow_log_schema_catalog()["columns"][0]["name"] == "event_time"


@pytest.mark.parametrize(
    ("sql", "code"),
    [
        ("SELECT count(*) AS total FROM logs CROSS JOIN params WHERE severity = params.\"level\"", None),
        ("WITH selected AS (SELECT body FROM logs) SELECT count(body) AS total FROM selected", None),
        ("SELECT count(*) total FROM logs", "LOG_QUERY_OUTPUT_ALIAS_MISMATCH"),
        ("SELECT logs.* AS raw FROM logs", "LOG_QUERY_OUTPUT_ALIAS_MISMATCH"),
        ("SELECT COLUMNS(*) AS raw FROM logs", "LOG_QUERY_OUTPUT_ALIAS_MISMATCH"),
        ("SELECT COLUMNS(c -> c LIKE '%body%') AS raw FROM logs", "LOG_QUERY_OUTPUT_ALIAS_MISMATCH"),
        ("SELECT ALL COLUMNS FROM logs", "LOG_QUERY_OUTPUT_ALIAS_MISMATCH"),
        ("WITH logs AS (SELECT body AS body FROM logs) SELECT body AS total FROM logs", "LOG_QUERY_FORBIDDEN_SOURCE"),
        ("SELECT count(*) AS total FROM logs; SELECT 1 AS other", "LOG_QUERY_MULTIPLE_STATEMENTS"),
        ("DELETE FROM logs", "LOG_QUERY_SQL_INVALID"),
        ("SELECT 'unterminated AS total FROM logs", "LOG_QUERY_SQL_INVALID"),
        ("SELECT count(*) AS total FROM read_csv('logs.csv')", "LOG_QUERY_FORBIDDEN_SOURCE"),
        ("SELECT load_extension('x') AS total FROM logs", "LOG_QUERY_FORBIDDEN_SOURCE"),
        ("SELECT read_csv_auto('logs.csv') AS total FROM logs", "LOG_QUERY_FORBIDDEN_SOURCE"),
        ("SELECT http_get('https://example.invalid') AS total FROM logs", "LOG_QUERY_FORBIDDEN_SOURCE"),
        ("SELECT glob('*.log') AS total FROM logs", "LOG_QUERY_FORBIDDEN_SOURCE"),
        ("SELECT system('echo unsafe') AS total FROM logs", "LOG_QUERY_FORBIDDEN_SOURCE"),
        ("SELECT shell('echo unsafe') AS total FROM logs", "LOG_QUERY_FORBIDDEN_SOURCE"),
        ("SELECT count(*) AS wrong FROM logs", "LOG_QUERY_OUTPUT_ALIAS_MISMATCH"),
        ("SELECT count(*) AS total FROM logs WHERE severity = params.\"missing\"", "LOG_QUERY_UNKNOWN_COLUMN"),
        ("SELECT count(*) AS total FROM logs WHERE missing = 1", "LOG_QUERY_UNKNOWN_COLUMN"),
        ("SELECT params.\"level\" AS total FROM logs AS params", "LOG_QUERY_UNKNOWN_COLUMN"),
    ],
)
def test_log_sql_static_contract(sql: str, code: str | None):
    diagnostics = validate_log_query(sql, ["total"], ["level"])
    if code is None:
        assert diagnostics == []
    else:
        assert diagnostics[0].code == code


def test_log_outputs_must_have_one_query_and_scalar_schema():
    definition = _log_definition()
    definition["spec"]["queries"].append({"id": "query-other", "name": "另一个", "sql": "SELECT 1 AS other FROM logs", "outputIds": ["output-count"]})
    definition["outputs"].append({"id": "output-other", "key": "other", "schema": {"type": "object", "properties": {}, "required": [], "additionalProperties": False}})
    issues = validate_workflow_document(_document(definition))
    codes = [item["code"] for item in issues]

    assert "LOG_QUERY_OUTPUT_NOT_UNIQUE" in codes
    assert "LOG_QUERY_OUTPUT_NOT_ASSIGNED" in codes
    assert "LOG_OUTPUT_SCHEMA_NOT_SCALAR" in codes


def test_log_inputs_must_be_scalar_and_calls_forbid_role_and_sample_count():
    definition = _log_definition()
    definition["inputs"][0]["schema"] = {"type": "array", "items": {"type": "string"}}
    document = _document(definition)
    call = document["workflow"]["nodes"][0]["collectionCalls"][0]
    call["deviceRoleId"] = "role-device"
    call["sampleCount"] = 2
    document["workflow"]["deviceRoles"] = [{"id": "role-device", "key": "device", "name": "设备"}]
    issues = validate_workflow_document(document)
    codes = [item["code"] for item in issues]

    assert "LOG_INPUT_SCHEMA_NOT_SCALAR" in codes
    assert "LOG_CALL_DEVICE_ROLE_UNSUPPORTED" in codes
    assert "LOG_CALL_SAMPLE_COUNT_UNSUPPORTED" in codes


def _log_definition() -> dict:
    return {
        "id": "collection-log",
        "revision": 1,
        "key": "log_summary",
        "metadata": {"name": "日志摘要"},
        "spec": {
            "collectionType": "log",
            "sqlDialect": "duckdb",
            "queries": [{"id": "query-count", "name": "错误计数", "sql": "SELECT count(*) AS error_count FROM logs", "outputIds": ["output-count"]}],
            "outputSamples": [{"id": "sample-1", "name": "空窗", "text": "raw log"}],
        },
        "inputs": [{"id": "input-level", "key": "level", "required": True, "schema": {"type": "string", "title": "等级"}}],
        "outputs": [{"id": "output-count", "key": "error_count", "required": True, "schema": {"type": "integer", "title": "错误数"}}],
    }


def _document(definition: dict) -> dict:
    normalized = normalize_collection_definition(definition)
    return normalize_workflow_document(
        {
            "documentType": "workflow_bundle",
            "workflow": {
                "id": "workflow-log",
                "revision": 1,
                "metadata": {"name": "日志工作流", "description": "检查日志"},
                "inputs": [],
                "deviceRoles": [],
                "nodes": [
                    {
                        "id": "step-log",
                        "name": "查询日志",
                        "description": "聚合日志",
                        "isStart": True,
                        "stepType": "expression",
                        "collectionCalls": [
                            {
                                "id": "call-log",
                                "key": "logs",
                                "name": "日志",
                                "definition": {"id": normalized["id"], "revision": normalized["revision"]},
                                "sampleCount": 1,
                                "inputBindings": {},
                            }
                        ],
                        "topology": [],
                    }
                ],
            },
            "collectionSnapshots": [normalized],
        }
    )
