from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class TypeSpec:
    kind: str
    item: "TypeSpec | None" = None
    properties: dict[str, "TypeSpec"] = field(default_factory=dict)
    options: tuple["TypeSpec", ...] = ()
    sample_count: int | None = None

    def serialize(self) -> dict[str, Any]:
        value: dict[str, Any] = {"kind": self.kind}
        if self.item is not None:
            value["item"] = self.item.serialize()
        if self.properties:
            value["properties"] = {key: item.serialize() for key, item in sorted(self.properties.items())}
        if self.options:
            value["options"] = [item.serialize() for item in self.options]
        if self.sample_count is not None:
            value["sampleCount"] = self.sample_count
        return value


ANY = TypeSpec("any")
NONE = TypeSpec("none")
BOOLEAN = TypeSpec("boolean")
STRING = TypeSpec("string")
INTEGER = TypeSpec("integer")
NUMBER = TypeSpec("number")


def array(item: TypeSpec = ANY, *, sample_count: int | None = None) -> TypeSpec:
    return TypeSpec("array", item=item, sample_count=sample_count)


def object_type(properties: dict[str, TypeSpec] | None = None, *, sample_count: int | None = None) -> TypeSpec:
    return TypeSpec("object", properties=properties or {}, sample_count=sample_count)


def union(*options: TypeSpec) -> TypeSpec:
    flattened: list[TypeSpec] = []
    for option in options:
        values = option.options if option.kind == "union" else (option,)
        for value in values:
            if value not in flattened:
                flattened.append(value)
    return flattened[0] if len(flattened) == 1 else TypeSpec("union", options=tuple(flattened))


def from_json_schema(schema: dict[str, Any]) -> TypeSpec:
    schema_type = schema.get("type")
    if isinstance(schema_type, list):
        options = []
        for item in schema_type:
            if item == "null":
                options.append(NONE)
            else:
                options.append(from_json_schema({**schema, "type": item}))
        return union(*options)
    if schema_type in {"string", "integer", "number", "boolean"}:
        return {"string": STRING, "integer": INTEGER, "number": NUMBER, "boolean": BOOLEAN}[schema_type]
    if schema_type == "array":
        return array(from_json_schema(schema.get("items", {})))
    if schema_type == "object":
        required = set(schema.get("required", []))
        properties = {
            key: value_type if key in required else union(value_type, NONE)
            for key, value in schema.get("properties", {}).items()
            for value_type in [from_json_schema(value)]
        }
        return object_type(properties)
    return ANY
