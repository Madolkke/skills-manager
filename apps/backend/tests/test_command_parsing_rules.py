"""命令选择、结果诊断及模板允许范围。"""
import pytest

from skillhub.models.errors import CommandParseError
from skillhub.models.rules.command_parsing import select_command, validate_result
from skillhub.models.rules.ttp_template import validate_template


def entry(identity="a", score=10, template="{{ value }}"):
    """模拟已有命令搜索的候选格式。"""
    return {"id": identity, "key": identity, "name": identity, "expression": "show <value>", "ttp": template,
            "complete": True, "match": {"exact": True}, "score": score, "consumedTokens": 2}


def test_selection():
    assert select_command([entry(), entry(), entry("b", 1)])["id"] == "a"
    assert select_command([entry(template=""), entry("b", 1)])["id"] == "b"
    for rows, code in [([], "COMMAND_NOT_FOUND"), ([{**entry(), "complete": False}], "COMMAND_NOT_FOUND"),
                       ([entry(template=" ")], "TTP_TEMPLATE_MISSING"), ([entry(), entry("b")], "COMMAND_AMBIGUOUS")]:
        with pytest.raises(CommandParseError) as exc:
            select_command(rows)
        assert exc.value.code == code
        if code == "COMMAND_AMBIGUOUS":
            assert [item["id"] for item in exc.value.candidates] == ["a", "b"]
            assert all("ttp" not in item for item in exc.value.candidates)


def test_schema_diagnostics():
    schema = {"type": "object", "properties": {"rows": {"type": "array", "items": {"type": "object",
              "properties": {"count": {"type": "integer"}}, "required": ["count"], "additionalProperties": False}}},
              "required": ["rows"], "additionalProperties": False}
    result = {"rows": [{"count": "4"}, {}, {"count": True}], "a/b~c": 1}
    checked = validate_result(result, schema)
    assert not checked["valid"]
    assert {item["path"] for item in checked["warnings"]} == {"/rows/0/count", "/rows/1/count", "/rows/2/count", "/a~1b~0c"}
    assert result["rows"][0]["count"] == "4"
    assert validate_result({"rows": [{"count": 4}]}, schema) == {"valid": True, "warnings": []}
    assert validate_result({}, {"type": "object", "properties": {}})["valid"] is True
    assert validate_result({}, schema)["valid"] is False
    assert validate_result([], {"type": "array", "items": {"type": "string"}})["warnings"][0]["code"] == "TTP_EMPTY_RESULT"


@pytest.mark.parametrize("template", [
    '<macro>raise Exception()</macro>{{ x }}', '<input load="text">data</input>{{ x }}',
    '<output format="json" returner="file"/>{{ x }}', '<extend template="x"/>{{ x }}',
    '<vars load="python">a=1</vars>{{ x }}', '<lookup name="x" include="file"/>{{ x }}',
    '<group macro="x">{{ x }}</group>', '<group functions="macro(x)">{{ x }}</group>',
    '<template name="a">{{ x }}</template><template name="b">{{ x }}</template>',
    '{{ x | macro("x") }}', '{{ x | print }}', '{{ x | unknown }}',
    '{{ x | re(__import__("os").getcwd()) }}', '{{ x | set(open("x")) }}',
    '{{ x | set(**{}) }}', '{{ x | re("[a-z]")', '<!DOCTYPE x>{{ x }}',
    '<group>{{ x }}</group><unknown/>', '<template base_path="/">{{ x }}</template>',
])
def test_unsupported_template_rejected(template):
    with pytest.raises(CommandParseError) as exc:
        validate_template(template)
    assert exc.value.code == "TTP_TEMPLATE_INVALID"


def test_allowed_template():
    assert '<group name="rows*">' in validate_template('<group name="rows*">\n{{ name | lower }} {{ count | DIGIT | to_int }}\n</group>')
