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
    required_properties: frozenset[str] = frozenset()

    def property_type(self, key: str) -> "TypeSpec":
        """Include absence only when an object property is read as a value."""
        value = self.properties[key]
        return value if key in self.required_properties else union(value, NONE)

    def serialize(self) -> dict[str, Any]:
        value: dict[str, Any] = {"kind": self.kind}
        if self.item is not None:
            value["item"] = self.item.serialize()
        if self.properties:
            value["properties"] = {key: self.property_type(key).serialize() for key in sorted(self.properties)}
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


def object_type(
    properties: dict[str, TypeSpec] | None = None, *, sample_count: int | None = None, required: frozenset[str] | None = None,
) -> TypeSpec:
    """Keep property presence separate from each property's declared value type."""
    values = properties or {}
    return TypeSpec("object", properties=values, sample_count=sample_count, required_properties=frozenset(values) if required is None else required)


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
        properties = {key: from_json_schema(value) for key, value in schema.get("properties", {}).items()}
        return object_type(properties, required=frozenset(schema.get("required", [])))
    return ANY


def type_spec_assignable_to_schema(source: TypeSpec, target: dict[str, Any]) -> bool:
    """Check whether an inferred expression type satisfies a JSON Schema."""
    target_type = target.get("type")
    if target_type is None or target.get("x-skillhub-legacy-loose"):
        return True
    if source.kind == "union":
        return all(type_spec_assignable_to_schema(option, target) for option in source.options)
    if source.kind == "any":
        return False
    if isinstance(target_type, list):
        return any(type_spec_assignable_to_schema(source, {**target, "type": item}) for item in target_type)
    if source.kind == "none":
        return target_type == "null"
    if source.kind != target_type and not (source.kind == "integer" and target_type == "number"):
        return False
    if source.kind == "array":
        return type_spec_assignable_to_schema(source.item or ANY, target.get("items", {}))
    if source.kind == "object":
        properties = target.get("properties", {})
        required = set(target.get("required", []))
        if not required.issubset(source.required_properties):
            return False
        return all(
            key not in source.properties or type_spec_assignable_to_schema(source.properties[key], child)
            for key, child in properties.items()
        )
    return True


def type_spec_from_serialized(value: dict[str, Any]) -> TypeSpec:
    """Restore a checker TypeSpec from the serialized validation result."""
    kind = str(value.get("kind", "any"))
    if kind == "array":
        return array(type_spec_from_serialized(value.get("item", {})), sample_count=value.get("sampleCount"))
    if kind == "object":
        return object_type({key: type_spec_from_serialized(item) for key, item in value.get("properties", {}).items()}, sample_count=value.get("sampleCount"))
    if kind == "union":
        options = [type_spec_from_serialized(item) for item in value.get("options", [])]
        return union(*options) if options else ANY
    return TypeSpec(kind, sample_count=value.get("sampleCount"))
