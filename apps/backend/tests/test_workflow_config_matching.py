from __future__ import annotations

from skillhub.models.rules.workflows import normalize_workflow_document, validate_workflow_document
from skillhub.models.rules.workflows.config_pattern import ConfigPatternError, parse_config_pattern
from skillhub.models.rules.workflows.config_validation import validate_config_spec


def test_config_pattern_extracts_named_captures_and_normalizes_spaces() -> None:
    parsed = parse_config_pattern(r"interface   <name> ip <address:\S+>")
    assert parsed.names == ("name", "address")
    assert parsed.regex == r"^interface\s+(?P<name>\S+)\s+ip\s+(?P<address>\S+)$"


def test_config_pattern_supports_escaped_brackets() -> None:
    parsed = parse_config_pattern(r"literal \<value\> <capture>")
    assert parsed.names == ("capture",)


def test_config_pattern_allows_regex_character_classes_and_nested_groups() -> None:
    assert parse_config_pattern(r"value <text:[^>]+>").names == ("text",)
    assert parse_config_pattern(r"value <text:(?P<inner>[^ ]+)>").names == ("text",)


def test_config_pattern_rejects_duplicate_and_invalid_names() -> None:
    for pattern, code in (("x <name> <name>", "CONFIG_CAPTURE_NAME_DUPLICATE"), ("x <_name>", "CONFIG_CAPTURE_NAME_INVALID"), ("x <items>", "CONFIG_COMMAND_NAME_RESERVED")):
        try:
            parse_config_pattern(pattern)
        except ConfigPatternError as exc:
            assert exc.code == code
        else:
            raise AssertionError("expected ConfigPatternError")


def test_config_validation_requires_exact_capture_map_and_scalar_schema() -> None:
    issues: list[dict[str, object]] = []
    validate_config_spec(
        {
            "collectionType": "config",
            "config": {"commands": [{"name": "interface", "unique": True, "pattern": "interface <name>", "captures": {"other": {"type": "object"}}, "children": []}]},
        },
        {"type": "collection", "id": "c1", "revision": 1},
        issues,
    )
    assert [item["code"] for item in issues] == ["CONFIG_CAPTURE_SCHEMA_NOT_SCALAR", "CONFIG_CAPTURE_SCHEMA_MISMATCH"]


def test_config_validation_detects_capture_child_conflict() -> None:
    issues: list[dict[str, object]] = []
    validate_config_spec(
        {
            "collectionType": "config",
            "config": {"commands": [{"name": "interface", "unique": True, "pattern": "interface <name>", "captures": {"name": {"type": "string"}}, "children": [{"name": "name", "unique": True, "pattern": "name", "captures": {}, "children": []}]}]},
        },
        {"type": "collection", "id": "c1", "revision": 1},
        issues,
    )
    assert any(item["code"] == "CONFIG_COMMAND_PROPERTY_CONFLICT" for item in issues)


def test_config_root_conflicts_are_scoped_by_device_role() -> None:
    definition = {
        "id": "config-1", "revision": 1, "key": "config", "metadata": {"name": "配置", "description": ""},
        "spec": {"collectionType": "config", "config": {"commands": [{"name": "interface", "unique": True, "pattern": "interface", "captures": {}, "children": []}]}},
        "inputs": [], "outputs": [],
    }
    document = normalize_workflow_document({
        "documentType": "workflow_bundle",
        "workflow": {
            "id": "workflow-config", "revision": 1, "metadata": {"name": "配置", "description": ""},
            "inputs": [], "deviceRoles": [{"id": "role-a", "key": "a", "name": "A"}, {"id": "role-b", "key": "b", "name": "B"}],
            "nodes": [{
                "id": "step", "name": "步骤", "description": "", "isStart": True, "stepType": "expression", "collectionCalls": [
                    {"id": "call-a", "key": "a", "name": "A", "definition": {"id": "config-1", "revision": 1}, "deviceRoleId": "role-a", "sampleCount": 1, "inputBindings": {}},
                    {"id": "call-b", "key": "b", "name": "B", "definition": {"id": "config-1", "revision": 1}, "deviceRoleId": "role-b", "sampleCount": 1, "inputBindings": {}},
                    {"id": "call-c", "key": "c", "name": "C", "definition": {"id": "config-1", "revision": 1}, "deviceRoleId": "role-a", "sampleCount": 1, "inputBindings": {}},
                ], "topology": [],
            }],
        },
        "collectionSnapshots": [definition],
    })
    issues = validate_workflow_document(document)
    conflicts = [item for item in issues if item["code"] == "CONFIG_ROOT_COMMAND_CONFLICT"]
    assert len(conflicts) == 1
    assert conflicts[0]["selection"]["itemId"] == "call-c"


def test_config_expression_index_errors_are_workflow_validation_errors() -> None:
    document = normalize_workflow_document({
        "documentType": "workflow_bundle",
        "workflow": {
            "id": "workflow-config", "revision": 1, "metadata": {"name": "配置", "description": ""}, "inputs": [], "deviceRoles": [],
            "nodes": [
                {"id": "step", "name": "步骤", "description": "", "isStart": True, "stepType": "expression", "collectionCalls": [{"id": "call", "key": "", "name": "配置", "definition": {"id": "config-1", "revision": 1}, "sampleCount": 1, "inputBindings": {}}], "topology": [{"id": "transition", "target": {"id": "done"}, "conditionText": "", "conditionExpression": "config.interface[1.5]"}]},
                {"id": "done", "name": "完成", "rootCause": "", "repairRecommendation": "", "nodeType": "conclusion"},
            ],
        },
        "collectionSnapshots": [{
            "id": "config-1", "revision": 1, "key": "config", "metadata": {"name": "配置", "description": ""},
            "spec": {"collectionType": "config", "config": {"commands": [{"name": "interface", "unique": False, "pattern": "interface", "captures": {}, "children": []}]}},
            "inputs": [], "outputs": [],
        }],
    })
    issues = validate_workflow_document(document)
    assert any(item["code"] == "CONFIG_ARRAY_INDEX_INVALID" and item["severity"] == "error" for item in issues)
