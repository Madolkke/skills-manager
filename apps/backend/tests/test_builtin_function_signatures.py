"""内置静态规则覆盖合法重载和非法调用，不执行函数体。"""
import pytest

from skillhub.models.rules.workflows.expression import validate_expression
from skillhub.models.rules.workflows.expression.registry import FUNCTIONS


@pytest.mark.parametrize('source', [
    "len('a')", "len([1])", "min(1, 2)", "min([1, 2])", "max('ab')", "max(1, 2, 3)",
    "min(iterable=[1], default=0)", "sum([1, 2])", "sum([1], start=2)",
    "any([True, 0])", "all([])", "sorted([2, 1], reverse=True)", "sorted('abc')", "list()", "list('abc')",
    "abs(-1)", "abs(value=1.2)", "round(1.25, 1)", "round(value=1.2, ndigits=0)",
    "str()", "str([1])", "int()", "int('ff', base=16)", "float()", "float('1')", "bool()", "bool({})",
])
def test_legal_builtin_overloads(source):
    assert validate_expression(source, {}, FUNCTIONS)['diagnostics'] == []


@pytest.mark.parametrize(('source', 'code'), [
    ("sum(1)", 'FUNCTION_ARGUMENT_TYPE_MISMATCH'), ("sum(['x'])", 'FUNCTION_ARGUMENT_TYPE_MISMATCH'),
    ("len(1)", 'FUNCTION_ARGUMENT_TYPE_MISMATCH'), ("len()", 'FUNCTION_REQUIRED_ARGUMENT'),
    ("min()", 'FUNCTION_REQUIRED_ARGUMENT'), ("max(1)", 'FUNCTION_ARGUMENT_TYPE_MISMATCH'),
    ("any(1)", 'FUNCTION_ARGUMENT_TYPE_MISMATCH'), ("all(False)", 'FUNCTION_ARGUMENT_TYPE_MISMATCH'),
    ("sorted(1)", 'FUNCTION_ARGUMENT_TYPE_MISMATCH'), ("list(1)", 'FUNCTION_ARGUMENT_TYPE_MISMATCH'),
    ("abs('1')", 'FUNCTION_ARGUMENT_TYPE_MISMATCH'), ("round(1, 'x')", 'FUNCTION_ARGUMENT_TYPE_MISMATCH'),
    ("str(1, 2)", 'FUNCTION_TOO_MANY_ARGUMENTS'), ("int([])", 'FUNCTION_ARGUMENT_TYPE_MISMATCH'),
    ("float({})", 'FUNCTION_ARGUMENT_TYPE_MISMATCH'), ("bool(1, 2)", 'FUNCTION_TOO_MANY_ARGUMENTS'),
    ("round(1, value=2)", 'FUNCTION_DUPLICATE_ARGUMENT'), ("sum([1], iterable=[2])", 'FUNCTION_DUPLICATE_ARGUMENT'),
    ("sum([1], missing=2)", 'FUNCTION_UNKNOWN_KEYWORD'), ("min(1, 2, default=3)", 'FUNCTION_UNKNOWN_KEYWORD'),
    ("min(1, 'x')", 'FUNCTION_ARGUMENT_TYPE_MISMATCH'), ("int(base=2)", 'FUNCTION_REQUIRED_ARGUMENT'),
    ("int(3, base=2)", 'FUNCTION_ARGUMENT_TYPE_MISMATCH'),
])
def test_invalid_builtin_calls(source, code):
    assert code in {item['code'] for item in validate_expression(source, {}, FUNCTIONS)['diagnostics']}


@pytest.mark.parametrize(('source', 'kind'), [("min(1, 2)", 'integer'), ("min(iterable=[1])", 'integer'), ("sorted([1])[0]", 'integer'), ("list('a')[0]", 'string')])
def test_generic_return_type(source, kind):
    assert validate_expression(source, {}, FUNCTIONS)['inferredType']['kind'] == kind


def test_empty_catalog_does_not_enable_builtins():
    assert validate_expression("len('x')", {}, {})['diagnostics'][0]['code'] == 'UNREGISTERED_CALL'


def test_unknown_type_is_tolerated():
    assert not any(item['code'].startswith('FUNCTION_') for item in validate_expression('sum(inputs.unknown)', {}, FUNCTIONS)['diagnostics'])
