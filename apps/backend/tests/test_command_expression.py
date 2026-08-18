from __future__ import annotations

import pytest

from skillhub.models.errors import InvariantError
from skillhub.models.rules.command_expression import (
    capture_catalog,
    match_command_expression,
    next_command_tokens,
    normalize_command_expression,
    parse_command_expression,
    search_command_expressions,
)


def test_parser_normalizes_quotes_groups_and_captures() -> None:
    expression = parse_command_expression('show {"interface status" | interface} [brief] <name>+')

    assert expression.normalized == 'show { "interface status" | interface } [brief] <name>+'
    result = match_command_expression(expression, 'show interface brief xe-0/0/1 ge-0/0/1')

    assert result is not None
    assert result.exact is True
    assert result.captures == {"name": ["xe-0/0/1", "ge-0/0/1"]}


def test_partial_match_accepts_an_incomplete_last_token() -> None:
    result = match_command_expression("show interface <name>", "show inter", partial=True, prefix=True)

    assert result is not None
    assert result.partial is True
    assert result.exact is False


def test_search_ranks_exact_matches_before_partial_matches() -> None:
    entries = [
        {"id": "partial", "source": "system", "expression": "show interface <name>"},
        {"id": "exact", "source": "system", "expression": "show interface status"},
    ]

    results = search_command_expressions(entries, "show interface status")

    assert [item["id"] for item in results][:1] == ["exact"]
    assert normalize_command_expression("show   interface status") == "show interface status"


def test_quoted_capture_keeps_outer_quotes_and_keywords_ignore_case() -> None:
    result = match_command_expression("show interface <value>", 'SHOW INTERFACE "xe 0/0/1"')

    assert result is not None
    assert result.exact is True
    assert result.captures == {"value": '"xe 0/0/1"'}
    assert parse_command_expression("SHOW Interface <value>").source == "SHOW Interface <value>"
    assert normalize_command_expression("SHOW Interface <value>") == "show interface <value>"


def test_expression_quotes_do_not_interpret_backslash_escapes() -> None:
    with pytest.raises(InvariantError):
        parse_command_expression('show "a\\"b"')

    with pytest.raises(InvariantError):
        match_command_expression("show <value>", 'show "unterminated')


def test_duplicate_capture_on_one_path_requires_repeat_marker() -> None:
    with pytest.raises(InvariantError):
        parse_command_expression("show <value> <value>")


def test_capture_catalog_derives_requiredness_across_choice_paths() -> None:
    assert capture_catalog("{ show <id> | display <id> }") == {
        "id": {"type": "string", "repeated": False, "optional": False}
    }
    assert capture_catalog("{ show <id> | display <name> }") == {
        "id": {"type": "string", "repeated": False, "optional": True},
        "name": {"type": "string", "repeated": False, "optional": True},
    }


def test_repeat_choice_accepts_each_branch_once() -> None:
    expression = "display { brief | detail | statistics } *"

    assert match_command_expression(expression, "display brief detail") is not None
    assert match_command_expression(expression, "display detail brief") is None
    assert match_command_expression(expression, "display detail detail") is None
    assert match_command_expression(expression, "display") is None


def test_optional_choice_repeat_allows_empty_but_not_duplicate_branches() -> None:
    expression = "display [ brief | detail ] *"

    assert match_command_expression(expression, "display") is not None
    assert match_command_expression(expression, "display brief detail") is not None
    assert match_command_expression(expression, "display detail brief") is None
    assert match_command_expression(expression, "display brief brief") is None


def test_repeated_capture_is_always_an_array() -> None:
    result = match_command_expression("display <interface>&<1-3>", "display ge0")

    assert result is not None
    assert result.captures == {"interface": ["ge0"]}

    with pytest.raises(InvariantError):
        parse_command_expression("display <interface>&<0-3>")

    spaced = match_command_expression("display <interface> & <1-3>", "display ge0 ge1")
    assert spaced is not None
    assert spaced.captures == {"interface": ["ge0", "ge1"]}


def test_repeated_choice_reusing_a_capture_derives_an_array_schema() -> None:
    assert capture_catalog("display { <value> | <value> } *")["value"] == {
        "type": "string",
        "repeated": True,
        "optional": False,
    }


def test_capture_schema_is_always_string_derived_from_angle_name() -> None:
    with pytest.raises(InvariantError):
        parse_command_expression("display <interface:integer>")


def test_brace_groups_require_real_choices_so_legacy_templates_are_not_migrated() -> None:
    with pytest.raises(InvariantError):
        parse_command_expression("display interface {{ interface_name }}")


def test_pipe_is_a_literal_outside_an_option_group() -> None:
    expression = parse_command_expression("display current-configuration | include peer")

    assert expression.normalized == "display current-configuration | include peer"
    assert match_command_expression(expression, "display current-configuration | include peer") is not None


def test_quoted_expression_punctuation_stays_a_literal_token() -> None:
    expression = parse_command_expression('show { "|" | "[" }')

    assert match_command_expression(expression, "show |") is not None
    assert match_command_expression(expression, "show [") is not None
    assert expression.normalized == 'show { "|" | "[" }'
    assert normalize_command_expression('show "interface"') == "show interface"


def test_match_rejects_excessive_token_input() -> None:
    with pytest.raises(InvariantError):
        match_command_expression("display <value>", " ".join("value" for _ in range(129)))

    with pytest.raises(InvariantError):
        parse_command_expression(" ".join("keyword" for _ in range(129)))


def test_next_tokens_follow_the_selected_choice_branch() -> None:
    expression = "show [brief | detail] status"

    assert next_command_tokens(expression, "show brief") == ["status"]
    assert next_command_tokens(expression, "show br") == ["brief"]


def test_ambiguous_match_exposes_all_capture_alternatives() -> None:
    result = match_command_expression("show { <value> | brief }", "show brief")

    assert result is not None
    assert result.ambiguous is True
    assert {tuple(item.items()) for item in result.alternatives} == {(), (("value", "brief"),)}
