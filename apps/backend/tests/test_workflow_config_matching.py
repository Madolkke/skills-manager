from __future__ import annotations

from skillhub.models.rules.workflows.config_pattern import ConfigPatternError, parse_config_pattern
from skillhub.models.rules.workflows.config_validation import validate_config_spec


def test_config_pattern_extracts_named_captures_and_normalizes_spaces() -> None:
    parsed = parse_config_pattern(r"interface   <name> ip <address:\S+>")
    assert parsed.names == ("name", "address")
    assert parsed.regex == r"^interface\s+(?P<name>\S+)\s+ip\s+(?P<address>\S+)$"


def test_config_pattern_supports_escaped_brackets() -> None:
    parsed = parse_config_pattern(r"literal \<value\> <capture>")
    assert parsed.names == ("capture",)


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
