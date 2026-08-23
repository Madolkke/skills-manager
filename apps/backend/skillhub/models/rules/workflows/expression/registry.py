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


def expression_contract() -> dict[str, Any]:
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
        "functions": FUNCTIONS,
        "methods": METHODS,
    }
