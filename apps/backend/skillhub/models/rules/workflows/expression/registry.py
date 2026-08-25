from __future__ import annotations

from typing import Any

FUNCTIONS: dict[str, dict[str, Any]] = {
    "len": {"parameters": ["sized"], "returns": "integer"},
    "min": {"parameters": ["iterable<T>"], "returns": "T"},
    "max": {"parameters": ["iterable<T>"], "returns": "T"},
    "sum": {"parameters": ["iterable<number>"], "returns": "number"},
    "any": {"parameters": ["iterable<any>"], "returns": "boolean"},
    "all": {"parameters": ["iterable<any>"], "returns": "boolean"},
    "sorted": {"parameters": ["iterable<T>"], "returns": "array<T>"},
    "abs": {"parameters": ["number"], "returns": "number"},
    "round": {"parameters": ["number", "integer?"], "returns": "number"},
    "str": {"parameters": ["any"], "returns": "string"},
    "int": {"parameters": ["any"], "returns": "integer"},
    "float": {"parameters": ["any"], "returns": "number"},
    "bool": {"parameters": ["any"], "returns": "boolean"},
    "list": {"parameters": ["iterable<T>"], "returns": "array<T>"},
}

METHODS: dict[str, dict[str, dict[str, Any]]] = {
    "string": {
        "lower": {"parameters": [], "returns": "string"},
        "upper": {"parameters": [], "returns": "string"},
        "strip": {"parameters": ["string?"], "returns": "string"},
        "startswith": {"parameters": ["string"], "returns": "boolean"},
        "endswith": {"parameters": ["string"], "returns": "boolean"},
        "split": {"parameters": ["string?"], "returns": "array<string>"},
        "replace": {"parameters": ["string", "string"], "returns": "string"},
    },
    "array": {
        "count": {"parameters": ["T"], "returns": "integer"},
        "index": {"parameters": ["T"], "returns": "integer"},
    },
    "object": {
        "get": {"parameters": ["string", "T?"], "returns": "T|none"},
        "keys": {"parameters": [], "returns": "array<string>"},
        "values": {"parameters": [], "returns": "array<T>"},
        "items": {"parameters": [], "returns": "array<array<any>>"},
    },
}


def builtin_function_documents() -> list[dict[str, Any]]:
    """Build the database seed documents from the legacy static signatures."""
    parameter_names = {
        "len": ["value"], "min": ["iterable"], "max": ["iterable"], "sum": ["iterable"],
        "any": ["iterable"], "all": ["iterable"], "sorted": ["iterable"], "abs": ["value"],
        "round": ["value", "ndigits"], "str": ["value"], "int": ["value"], "float": ["value"],
        "bool": ["value"], "list": ["iterable"],
    }
    return_schema = {
        "integer": {"type": "integer"},
        "number": {"type": "number"},
        "string": {"type": "string"},
        "boolean": {"type": "boolean"},
    }
    documents: list[dict[str, Any]] = []
    for name, signature in FUNCTIONS.items():
        names = parameter_names.get(name, [f"arg{index}" for index, _ in enumerate(signature.get("parameters", []))])
        properties = {
            parameter: {"type": "array", "items": {"type": "string"}} if "iterable" in str(spec)
            else {"type": "number"} if "number" in str(spec)
            else {"type": "integer"} if "integer" in str(spec)
            else {"type": "object", "additionalProperties": True, "x-skillhub-legacy-loose": True} if "any" in str(spec) or "sized" in str(spec)
            else {"type": "string"}
            for parameter, spec in zip(names, signature.get("parameters", []))
        }
        required = [parameter for parameter, spec in zip(names, signature.get("parameters", [])) if not str(spec).endswith("?")]
        result_schema = return_schema.get(signature.get("returns"), {"type": "string"})
        if str(signature.get("returns", "")).startswith("array"):
            result_schema = {"type": "array", "items": {"type": "string"}}
        documents.append({
            "name": name,
            "description": f"内置表达式函数 {name}。",
            "parameterSchema": {"type": "object", "properties": properties, "required": required, "additionalProperties": False},
            "returnSchema": result_schema,
            "body": f"# Built-in expression function: {name}",
            "language": "python",
            "isBuiltin": True,
            "enabled": True,
        })
    return documents


def expression_contract() -> dict[str, Any]:
    return expression_contract_with_functions(FUNCTIONS)


def expression_contract_with_functions(functions: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "contractVersion": 1,
        "language": "python-eval",
        "roots": ["inputs", "outputs", "config", "topo"],
        "typeAlgebra": ["any", "none", "string", "integer", "number", "boolean", "array<T>", "fixed-array<T>", "object", "union", "TypeVar", "optional", "variadic"],
        "outputModel": {
            "single": "outputs.<callKey>.<field>",
            "multiple": "outputs.<callKey>[<index>].<field>",
            "indexing": "zero-based Python indexing, including negative indexes",
        },
        "functions": functions,
        "methods": METHODS,
        "functionExecution": "Function bodies are stored as text and are not executed.",
    }
