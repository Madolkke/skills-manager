from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Any

from .environment import expression_root_types
from .registry import FUNCTIONS, METHODS
from .types import ANY, BOOLEAN, INTEGER, NONE, NUMBER, STRING, TypeSpec, array, object_type, union

SAMPLE_INDEX_DIAGNOSTIC_CODES = frozenset(
    {"SAMPLE_INDEX_REQUIRED", "SAMPLE_INDEX_NOT_ALLOWED", "SAMPLE_INDEX_OUT_OF_RANGE", "INVALID_SAMPLE_INDEX_TYPE"}
)


@dataclass(frozen=True)
class Diagnostic:
    code: str
    message: str
    start: int
    end: int

    def serialize(self) -> dict[str, Any]:
        return {"severity": "warning", "code": self.code, "message": self.message, "start": self.start, "end": self.end}


def validate_expression(source: str, environment: dict[str, Any], functions: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    if not source.strip():
        return {"inferredType": NONE.serialize(), "diagnostics": []}
    try:
        tree = ast.parse(source, mode="eval")
    except SyntaxError as exc:
        start = max((exc.offset or 1) - 1, 0)
        return {"inferredType": ANY.serialize(), "diagnostics": [Diagnostic("PYTHON_SYNTAX", exc.msg, start, start + 1).serialize()]}
    checker = _Checker(source, expression_root_types(environment), functions or FUNCTIONS)
    inferred = checker.infer(tree.body)
    return {"inferredType": inferred.serialize(), "diagnostics": [item.serialize() for item in checker.diagnostics]}


class _Checker:
    def __init__(self, source: str, roots: dict[str, TypeSpec], functions: dict[str, dict[str, Any]]) -> None:
        self.source = source
        self.scopes = [roots]
        self.diagnostics: list[Diagnostic] = []
        self.functions = functions

    def infer(self, node: ast.AST) -> TypeSpec:
        method = getattr(self, f"infer_{type(node).__name__}", None)
        if method is None:
            self.warn(node, "UNSUPPORTED_EXPRESSION", f"暂不支持表达式节点 {type(node).__name__}。")
            return ANY
        return method(node)

    def infer_Constant(self, node: ast.Constant) -> TypeSpec:
        if isinstance(node.value, bool):
            return BOOLEAN
        if isinstance(node.value, int):
            return INTEGER
        if isinstance(node.value, float):
            return NUMBER
        if isinstance(node.value, str):
            return STRING
        if node.value is None:
            return NONE
        return ANY

    def infer_Name(self, node: ast.Name) -> TypeSpec:
        for scope in reversed(self.scopes):
            if node.id in scope:
                return scope[node.id]
        if node.id in self.functions:
            return TypeSpec("function")
        self.warn(node, "UNKNOWN_NAME", f"未知名称“{node.id}”。")
        return ANY

    def infer_Attribute(self, node: ast.Attribute) -> TypeSpec:
        if node.attr.startswith("_"):
            self.warn(node, "PRIVATE_ACCESS", "不允许访问私有或反射属性。")
            return ANY
        owner = self.infer(node.value)
        if owner.kind == "union":
            return union(*(self._attribute(option, node) for option in owner.options))
        return self._attribute(owner, node)

    def infer_Subscript(self, node: ast.Subscript) -> TypeSpec:
        owner = self.infer(node.value)
        if _is_config_expression(node.value) and isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str):
            self.warn(node.slice, "CONFIG_STRING_SUBSCRIPT_FORBIDDEN", "config 只支持点号访问字段，不支持字符串下标。")
        index = self.infer(node.slice)
        if owner.sample_count == 1 and owner.kind == "object":
            self.warn(node, "SAMPLE_INDEX_NOT_ALLOWED", "单次采集输出不允许使用结果下标。")
            return owner
        if isinstance(node.slice, ast.Slice):
            return array(owner.item or ANY, sample_count=owner.sample_count) if owner.kind == "array" else owner
        if owner.kind == "array":
            if owner.sample_count is not None:
                if not _integer_index_type(index):
                    self.warn(node.slice, "INVALID_SAMPLE_INDEX_TYPE", "采集结果下标必须是整数。")
                literal = _integer_literal(node.slice)
                if literal is not None and not -owner.sample_count <= literal < owner.sample_count:
                    self.warn(node.slice, "SAMPLE_INDEX_OUT_OF_RANGE", f"采集结果下标 {literal} 超出范围 {-owner.sample_count}..{owner.sample_count - 1}。")
            elif index.kind != "integer":
                self.warn(node.slice, "CONFIG_ARRAY_INDEX_INVALID", "config 数组只允许使用整数下标。")
            return owner.item or ANY
        if owner.kind == "object" and isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str):
            return owner.properties.get(node.slice.value, ANY)
        if isinstance(node.slice, ast.Slice):
            return owner
        return ANY

    def infer_Slice(self, node: ast.Slice) -> TypeSpec:
        for value in (node.lower, node.upper, node.step):
            if value:
                self.infer(value)
        return ANY

    def infer_List(self, node: ast.List) -> TypeSpec:
        return array(union(*(self.infer(item) for item in node.elts)) if node.elts else ANY)

    infer_Tuple = infer_List
    infer_Set = infer_List

    def infer_Dict(self, node: ast.Dict) -> TypeSpec:
        return object_type(
            {str(key.value): self.infer(value) for key, value in zip(node.keys, node.values) if isinstance(key, ast.Constant) and isinstance(key.value, str)}
        )

    def infer_JoinedStr(self, node: ast.JoinedStr) -> TypeSpec:
        for value in node.values:
            self.infer(value)
        return STRING

    def infer_FormattedValue(self, node: ast.FormattedValue) -> TypeSpec:
        self.infer(node.value)
        if node.format_spec:
            self.infer(node.format_spec)
        return STRING

    def infer_BoolOp(self, node: ast.BoolOp) -> TypeSpec:
        for value in node.values:
            self.infer(value)
        return BOOLEAN

    def infer_Compare(self, node: ast.Compare) -> TypeSpec:
        self.infer(node.left)
        for value in node.comparators:
            self.infer(value)
        return BOOLEAN

    def infer_UnaryOp(self, node: ast.UnaryOp) -> TypeSpec:
        value = self.infer(node.operand)
        return BOOLEAN if isinstance(node.op, ast.Not) else value

    def infer_BinOp(self, node: ast.BinOp) -> TypeSpec:
        left, right = self.infer(node.left), self.infer(node.right)
        if isinstance(node.op, ast.Add) and left.kind == right.kind == "string":
            return STRING
        if left.kind in {"integer", "number"} and right.kind in {"integer", "number"}:
            return INTEGER if left.kind == right.kind == "integer" and not isinstance(node.op, ast.Div) else NUMBER
        return ANY

    def infer_IfExp(self, node: ast.IfExp) -> TypeSpec:
        self.infer(node.test)
        return union(self.infer(node.body), self.infer(node.orelse))

    def infer_Call(self, node: ast.Call) -> TypeSpec:
        for argument in [*node.args, *(keyword.value for keyword in node.keywords)]:
            self.infer(argument)
        if isinstance(node.func, ast.Name):
            signature = self.functions.get(node.func.id)
            if not signature:
                self.warn(node.func, "UNREGISTERED_CALL", f"函数“{node.func.id}”未注册。")
                return ANY
            self._validate_call_arguments(node, signature)
            return self._return_type(signature.get("returns", "any"), node.args[0] if node.args else None, signature.get("returnSchema"))
        if isinstance(node.func, ast.Attribute):
            owner = self.infer(node.func.value)
            signature = METHODS.get(owner.kind, {}).get(node.func.attr)
            if owner.kind == "any" and signature is None:
                signature = next((methods[node.func.attr] for methods in METHODS.values() if node.func.attr in methods), None)
            if not signature:
                self.warn(node.func, "UNREGISTERED_METHOD", f"类型 {owner.kind} 不支持方法“{node.func.attr}”。")
                return ANY
            return self._return_type(signature["returns"], node.func.value)
        self.warn(node.func, "UNREGISTERED_CALL", "只允许调用已注册函数或方法。")
        return ANY

    def infer_Lambda(self, node: ast.Lambda) -> TypeSpec:
        self.warn(node, "FORBIDDEN_LAMBDA", "不允许使用 lambda。")
        return ANY

    def infer_NamedExpr(self, node: ast.NamedExpr) -> TypeSpec:
        self.warn(node, "FORBIDDEN_WALRUS", "不允许使用海象运算符。")
        return self.infer(node.value)

    def infer_ListComp(self, node: ast.ListComp) -> TypeSpec:
        return array(self._comprehension(node.elt, node.generators))

    infer_SetComp = infer_ListComp
    infer_GeneratorExp = infer_ListComp

    def infer_DictComp(self, node: ast.DictComp) -> TypeSpec:
        self._comprehension(node.value, node.generators)
        return object_type()

    def _comprehension(self, value: ast.AST, generators: list[ast.comprehension]) -> TypeSpec:
        scope: dict[str, TypeSpec] = {}
        self.scopes.append(scope)
        for generator in generators:
            iterable = self.infer(generator.iter)
            if isinstance(generator.target, ast.Name):
                scope[generator.target.id] = iterable.item or ANY
            for condition in generator.ifs:
                self.infer(condition)
        result = self.infer(value)
        self.scopes.pop()
        return result

    def _attribute(self, owner: TypeSpec, node: ast.Attribute) -> TypeSpec:
        if owner.kind == "array" and owner.sample_count is not None:
            self.warn(node, "SAMPLE_INDEX_REQUIRED", "多次采集输出必须先指定结果下标。")
            return self._attribute(owner.item or ANY, node)
        if owner.kind == "object":
            if node.attr in owner.properties:
                return owner.properties[node.attr]
            if node.attr in METHODS["object"]:
                return TypeSpec("method")
            self.warn(node, "UNKNOWN_PROPERTY", f"对象不存在属性“{node.attr}”。")
        if owner.kind == "none":
            return NONE
        return ANY

    def _return_type(self, value: str, source: ast.AST | None, return_schema: dict[str, Any] | None = None) -> TypeSpec:
        if value not in {"T"} and not value.startswith("array<") and isinstance(return_schema, dict) and return_schema.get("type"):
            from .types import from_json_schema

            return from_json_schema(return_schema)
        if value == "integer":
            return INTEGER
        if value == "number":
            return NUMBER
        if value == "string":
            return STRING
        if value == "boolean":
            return BOOLEAN
        if value.startswith("array"):
            inferred = self.infer(source) if source else ANY
            return array(inferred.item or ANY)
        if value == "T" and source:
            return self.infer(source).item or ANY
        if value == "T|none" and source:
            return union(self.infer(source), NONE)
        return ANY

    def _validate_call_arguments(self, node: ast.Call, signature: dict[str, Any]) -> None:
        schema = signature.get("parameterSchema", {})
        # Legacy in-process signatures only describe abstract types.  They do
        # not carry stable parameter names, so keep their historical arity
        # behavior and apply named-argument checks to database-backed schemas.
        if not isinstance(schema, dict) or not isinstance(schema.get("properties"), dict):
            return
        properties = schema.get("properties", {}) if isinstance(schema, dict) else {}
        names = list(properties) if isinstance(properties, dict) else list(signature.get("parameters", []))
        if len(node.args) > len(names):
            self.warn(node, "FUNCTION_TOO_MANY_ARGUMENTS", "函数调用位置参数数量超过声明数量。")
        seen = set(names[: len(node.args)])
        for index, argument in enumerate(node.args):
            if index < len(names) and isinstance(properties.get(names[index]), dict) and not _schema_accepts_type(properties[names[index]], self.infer(argument)):
                self.warn(argument, "FUNCTION_ARGUMENT_TYPE_MISMATCH", f"参数“{names[index]}”的类型与函数声明不兼容。")
        for keyword_node in node.keywords:
            if keyword_node.arg is None or keyword_node.arg not in names:
                self.warn(keyword_node, "FUNCTION_UNKNOWN_KEYWORD", "函数调用包含未声明的关键字参数。")
            elif keyword_node.arg in seen:
                self.warn(keyword_node, "FUNCTION_DUPLICATE_ARGUMENT", "函数参数被重复提供。")
            else:
                seen.add(keyword_node.arg)
                if isinstance(properties.get(keyword_node.arg), dict) and not _schema_accepts_type(properties[keyword_node.arg], self.infer(keyword_node.value)):
                    self.warn(keyword_node.value, "FUNCTION_ARGUMENT_TYPE_MISMATCH", f"参数“{keyword_node.arg}”的类型与函数声明不兼容。")
        required = set(schema.get("required", [])) if isinstance(schema, dict) else set()
        for missing in sorted(required - seen):
            self.warn(node, "FUNCTION_REQUIRED_ARGUMENT", f"函数缺少必填参数“{missing}”。")

    def warn(self, node: ast.AST, code: str, message: str) -> None:
        start = _offset(self.source, getattr(node, "lineno", 1), getattr(node, "col_offset", 0))
        end = _offset(self.source, getattr(node, "end_lineno", 1), getattr(node, "end_col_offset", getattr(node, "col_offset", 0) + 1))
        self.diagnostics.append(Diagnostic(code, message, start, max(end, start + 1)))


def _offset(source: str, line: int, column: int) -> int:
    return sum(len(item) + 1 for item in source.splitlines()[: max(line - 1, 0)]) + column


def _is_config_expression(node: ast.AST) -> bool:
    while isinstance(node, ast.Attribute):
        node = node.value
    while isinstance(node, ast.Subscript):
        node = node.value
        while isinstance(node, ast.Attribute):
            node = node.value
    return isinstance(node, ast.Name) and node.id == "config"


def _integer_index_type(value: TypeSpec) -> bool:
    if value.kind in {"any", "integer"}:
        return True
    return value.kind == "union" and all(option.kind == "integer" for option in value.options)


def _schema_accepts_type(schema: dict[str, Any], actual: TypeSpec) -> bool:
    """Check the small JSON-Schema/type algebra intersection used by calls."""
    if schema.get("x-skillhub-legacy-loose") or actual.kind == "any":
        return True
    expected = schema.get("type")
    if expected == "number":
        return actual.kind in {"integer", "number"}
    if expected in {"string", "integer", "boolean", "object", "array"}:
        return actual.kind == expected
    return True


def _integer_literal(node: ast.AST) -> int | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, int) and not isinstance(node.value, bool):
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.operand, ast.Constant):
        value = node.operand.value
        if isinstance(value, int) and not isinstance(value, bool):
            if isinstance(node.op, ast.USub):
                return -value
            if isinstance(node.op, ast.UAdd):
                return value
    return None
