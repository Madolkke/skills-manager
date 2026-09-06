from copy import deepcopy

import pytest

from skillhub.models.errors import InvariantError
from skillhub.models.rules.workflows import (
    normalize_workflow_document,
    normalize_workflow_import_bundle,
    validate_workflow_document,
    validate_workflow_import_references,
)
from skillhub.models.rules.workflows.expression import validate_binding_expression, validate_expression
from skillhub.models.rules.workflows.expression.types import from_json_schema, type_spec_assignable_to_schema
from skillhub.models.rules.workflows.templates import iter_template_expressions, validate_template
from tests import test_workflow_rules as workflow_fixtures


def object_schema(required: list[str]) -> dict:
    """Build an object whose property presence can vary independently."""
    return {
        "type": "object", "title": "Payload", "properties": {"name": {"type": "string", "title": "Name"}},
        "required": required, "additionalProperties": False,
    }


@pytest.mark.parametrize("required", [[], ["name"]])
def test_identical_object_schema_is_assignable(required: list[str]) -> None:
    schema = object_schema(required)
    assert type_spec_assignable_to_schema(from_json_schema(schema), schema)


def test_optional_source_cannot_satisfy_required_target() -> None:
    assert not type_spec_assignable_to_schema(from_json_schema(object_schema([])), object_schema(["name"]))


def test_nested_optional_properties_and_explicit_null_stay_distinct() -> None:
    schema = {
        "type": "object", "properties": {"details": object_schema([])}, "required": [], "additionalProperties": False,
    }
    assert validate_binding_expression("inputs.payload", {"inputs": {"payload": schema}}, schema)["assignable"]
    assert not validate_binding_expression('{"name": None}', {}, object_schema([]))["assignable"]
    assert not validate_binding_expression("inputs.payload.name", {"inputs": {"payload": object_schema([])}}, {"type": "string"})["assignable"]


def test_operand_union_preserves_incompatible_branches_and_boolean_operations() -> None:
    environment = {"inputs": {"flag": {"type": "boolean"}}}
    result = validate_binding_expression('inputs.flag and "value"', environment, {"type": "string"})
    assert not result["assignable"]
    assert result["inferredType"]["kind"] == "union"
    assert validate_binding_expression("inputs.flag or False", environment, {"type": "boolean"})["assignable"]


def test_optional_field_serialization_keeps_public_contract() -> None:
    result = validate_expression("inputs.payload", {"inputs": {"payload": object_schema([])}})
    assert result["inferredType"] == {
        "kind": "object", "properties": {"name": {"kind": "union", "options": [{"kind": "string"}, {"kind": "none"}]}},
    }
    assert validate_expression("inputs.payload.name", {"inputs": {"payload": object_schema([])}})["inferredType"]["kind"] == "union"


@pytest.mark.parametrize(("expression", "target"), [
    ("inputs.payload", object_schema([])),
    ('"a,b".split(",")', {"type": "array", "title": "Names", "items": {"type": "string"}}),
    ('"" or "fallback"', {"type": "string", "title": "Name"}),
    ('"ready" and "value"', {"type": "string", "title": "Name"}),
])
def test_import_accepts_valid_expression_binding(expression: str, target: dict) -> None:
    bundle = normalize_workflow_import_bundle(workflow_fixtures.WorkflowRulesTest()._import_bundle())
    bundle["workflow"]["inputs"].append({"id": "payload", "key": "payload", "required": True, "schema": object_schema([])})
    bundle["collections"][0]["inputs"][0]["schema"] = deepcopy(target)
    bundle["workflow"]["nodes"][0]["collectionCalls"][0]["inputBindings"]["collection-input-interface"] = {
        "kind": "expression", "reference": {}, "expression": expression,
    }
    validate_workflow_import_references(normalize_workflow_import_bundle(bundle))


def test_import_rejects_optional_object_to_required_object() -> None:
    with pytest.raises(InvariantError, match="Schema is incompatible"):
        test_import_accepts_valid_expression_binding("inputs.payload", object_schema(["name"]))


def test_workflow_binding_validation_preserves_optional_presence() -> None:
    document = normalize_workflow_document(workflow_fixtures.WorkflowRulesTest()._document())
    document["workflow"]["inputs"][0]["schema"] = object_schema([])
    document["collectionSnapshots"][0]["inputs"][0]["schema"] = object_schema([])
    document["workflow"]["nodes"][0]["collectionCalls"][0]["inputBindings"]["opaque-parameter-id"] = {
        "kind": "expression", "reference": {}, "expression": "inputs.interface_name",
    }
    assert not any(item["code"] == "INCOMPATIBLE_BINDING_SCHEMA" for item in validate_workflow_document(document))
    document["collectionSnapshots"][0]["inputs"][0]["schema"] = object_schema(["name"])
    assert any(item["code"] == "INCOMPATIBLE_BINDING_SCHEMA" for item in validate_workflow_document(document))


@pytest.mark.parametrize("source", [
    '{{ {"a": {"b": 1}} }}',
    '{{ "}}" }}',
    "{{ '}}' }}",
    '{{ """}}""" }}',
    "{{ '''}}''' }}",
    '{{ "escaped \\\" }}" }}',
    '{{ ["}}", {"a": 1}] }}',
])
def test_template_delimiters_inside_expression_are_preserved(source: str) -> None:
    assert validate_template(source, {}) == []


@pytest.mark.parametrize(("source", "codes"), [
    ("plain }} text", ["TEMPLATE_UNEXPECTED_CLOSE"]),
    ("{{}}", ["TEMPLATE_EMPTY_EXPRESSION"]),
    ("{{   }}", ["TEMPLATE_EMPTY_EXPRESSION"]),
    ("{{", ["TEMPLATE_UNCLOSED"]),
    ('{{ "unterminated }}', ["TEMPLATE_UNCLOSED"]),
    ("{{ 1 }} }}", ["TEMPLATE_UNEXPECTED_CLOSE"]),
])
def test_template_reports_delimiter_errors(source: str, codes: list[str]) -> None:
    assert [item["code"] for item in validate_template(source, {})] == codes


def test_template_diagnostic_offsets_follow_original_source() -> None:
    source = 'Result: {{ "}}" }} next {{ inputs.missing }} }}'
    diagnostics = validate_template(source, {"inputs": {}})
    assert [(item["code"], source[item["start"]:item["end"]]) for item in diagnostics] == [
        ("UNKNOWN_PROPERTY", "inputs.missing"), ("TEMPLATE_UNEXPECTED_CLOSE", "}}"),
    ]


def utf16_slice(source: str, start: int, end: int) -> str:
    """Read frontend-style offsets without assuming one code unit per character."""
    return source.encode("utf-16-le")[start * 2:end * 2].decode("utf-16-le")


def test_unicode_expression_and_template_offsets_use_utf16() -> None:
    expression = '"中文😀" + inputs.missing'
    diagnostic = validate_expression(expression, {"inputs": {}})["diagnostics"][0]
    assert utf16_slice(expression, diagnostic["start"], diagnostic["end"]) == "inputs.missing"
    source = "前缀😀 {{ " + expression + " }} 尾部😀 }}"
    diagnostics = validate_template(source, {"inputs": {}})
    assert [(item["code"], utf16_slice(source, item["start"], item["end"])) for item in diagnostics] == [
        ("UNKNOWN_PROPERTY", "inputs.missing"), ("TEMPLATE_UNEXPECTED_CLOSE", "}}"),
    ]


def test_unicode_syntax_error_and_empty_template_offsets_use_utf16() -> None:
    expression = '"中文😀" + * 1'
    diagnostic = validate_expression(expression, {})["diagnostics"][0]
    assert utf16_slice(expression, diagnostic["start"], diagnostic["end"]) == "*"
    source = "😀 {{}} {{"
    diagnostics = validate_template(source, {})
    assert diagnostics[0]["start"] == diagnostics[0]["end"] == 5
    assert utf16_slice(source, diagnostics[1]["start"], diagnostics[1]["end"]) == "{{"


def test_multiline_unicode_offsets_and_internal_template_slices() -> None:
    expression = '("中文😀"\n + inputs.missing)'
    diagnostic = validate_expression(expression, {"inputs": {}})["diagnostics"][0]
    assert utf16_slice(expression, diagnostic["start"], diagnostic["end"]) == "inputs.missing"
    source = "😀 {{ " + expression + " }}"
    [(text, start, end)] = list(iter_template_expressions(source))
    assert text == source[start:end] == " " + expression + " "
    diagnostic = validate_template(source, {"inputs": {}})[0]
    assert utf16_slice(source, diagnostic["start"], diagnostic["end"]) == "inputs.missing"
