from __future__ import annotations

import keyword
from collections.abc import Mapping
from typing import Any

from sqlalchemy import delete, insert, select, update

from skillhub.models.entities import new_id, utc_now
from skillhub.models.errors import ConflictError, InvariantError, NotFoundError
from skillhub.models.schema import orm


class ExpressionFunctionStoreMixin:
    def list_expression_functions(self, *, include_disabled: bool = True) -> list[dict[str, Any]]:
        with self._read_session() as session:
            statement = select(orm.ExpressionFunction).order_by(orm.ExpressionFunction.name)
            if not include_disabled:
                statement = statement.where(orm.ExpressionFunction.enabled.is_(True))
            return [_expression_function_row(item) for item in session.execute(statement).scalars()]

    def get_expression_function(self, *, function_id: str) -> dict[str, Any]:
        with self._read_session() as session:
            item = session.get(orm.ExpressionFunction, function_id)
            if item is None:
                raise NotFoundError(f"Expression function does not exist: {function_id}")
            return _expression_function_row(item)

    def create_expression_function(self, *, payload: Mapping[str, Any], actor: str) -> dict[str, Any]:
        values = _clean_expression_function_payload(payload, actor=actor, function_id=payload.get("id"))
        with self._write_session() as session:
            try:
                session.execute(insert(orm.ExpressionFunction).values(**values))
            except Exception as exc:
                if _is_integrity_error(exc):
                    raise ConflictError("Expression function name already exists.") from exc
                raise
            session.flush()
            return _expression_function_row(session.get(orm.ExpressionFunction, values["id"]))

    def update_expression_function(self, *, function_id: str, payload: Mapping[str, Any], actor: str) -> dict[str, Any]:
        with self._write_session() as session:
            item = session.get(orm.ExpressionFunction, function_id)
            if item is None:
                raise NotFoundError(f"Expression function does not exist: {function_id}")
            current = _expression_function_row(item)
            values = _clean_expression_function_payload({**current, **dict(payload)}, actor=actor, function_id=function_id)
            values.pop("id", None)
            values["updated_at"] = utc_now()
            try:
                session.execute(update(orm.ExpressionFunction).where(orm.ExpressionFunction.id == function_id).values(**values))
            except Exception as exc:
                if _is_integrity_error(exc):
                    raise ConflictError("Expression function name already exists.") from exc
                raise
            session.flush()
            session.refresh(item)
            return _expression_function_row(item)

    def delete_expression_function(self, *, function_id: str) -> dict[str, Any]:
        with self._write_session() as session:
            if session.get(orm.ExpressionFunction, function_id) is None:
                raise NotFoundError(f"Expression function does not exist: {function_id}")
            session.execute(delete(orm.ExpressionFunction).where(orm.ExpressionFunction.id == function_id))
        return {"id": function_id, "deleted": True}

    def expression_function_contract(self) -> dict[str, dict[str, Any]]:
        return {
            item["name"]: {
                "name": item["name"],
                "parameters": _parameter_names(item["parameter_schema"]),
                "parameterSchema": item["parameter_schema"],
                "returns": item["return_schema"].get("type", "any"),
                "returnSchema": item["return_schema"],
                "description": item["description"],
                "enabled": item["enabled"],
                "isBuiltin": item["is_builtin"],
                "language": item["language"],
                "bodyLength": len(item["body"]),
            }
            for item in self.list_expression_functions(include_disabled=False)
        }


def _clean_expression_function_payload(payload: Mapping[str, Any], *, actor: str, function_id: str | None) -> dict[str, Any]:
    name = str(payload.get("name", "")).strip()
    if not name.isidentifier() or keyword.iskeyword(name) or name.startswith("_"):
        raise InvariantError("Expression function name must be a Python identifier, not a keyword or private name.")
    body = str(payload.get("body", ""))
    if not body.strip() or len(body) > 50000:
        raise InvariantError("Expression function body must be non-empty and at most 50000 characters.")
    language = str(payload.get("language", "python")).strip()
    if not language or len(language) > 40:
        raise InvariantError("Expression function language is invalid.")
    parameter_schema = _validate_schema(payload.get("parameter_schema", payload.get("parameterSchema", {})), root_object=True, label="parameter_schema", identifier_properties=True)
    return_schema = _validate_schema(payload.get("return_schema", payload.get("returnSchema", {})), root_object=False, label="return_schema")
    now = utc_now()
    return {
        "id": function_id or new_id("expression-function"),
        "name": name,
        "description": str(payload.get("description", "")).strip(),
        "parameter_schema": parameter_schema,
        "return_schema": return_schema,
        "body": body,
        "language": language,
        "is_builtin": bool(payload.get("is_builtin", payload.get("isBuiltin", False))),
        "enabled": bool(payload.get("enabled", True)),
        "created_by": str(payload.get("created_by", payload.get("createdBy", actor))),
        "updated_by": actor,
        "created_at": payload.get("created_at", payload.get("createdAt", now)),
        "updated_at": now,
    }


def _validate_schema(value: Any, *, root_object: bool, label: str, identifier_properties: bool = False) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise InvariantError(f"{label} must be a JSON Schema object.")
    result = dict(value)
    if root_object and result.get("type") != "object":
        raise InvariantError(f"{label} root type must be object.")
    schema_type = result.get("type")
    if schema_type not in {"string", "integer", "number", "boolean", "object", "array"}:
        raise InvariantError(f"{label} contains an unsupported type.")
    if schema_type == "object":
        properties = result.get("properties")
        required = result.get("required", [])
        if not isinstance(properties, Mapping) or not isinstance(required, list):
            raise InvariantError(f"{label} object requires properties and required.")
        if not all(isinstance(item, str) for item in required) or len(required) != len(set(required)) or not set(required).issubset(properties):
            raise InvariantError(f"{label}.required must contain unique property names.")
        normalized_properties: dict[str, Any] = {}
        for key, child in properties.items():
            property_name = str(key)
            if identifier_properties and (not property_name.isidentifier() or keyword.iskeyword(property_name) or property_name.startswith("_")):
                raise InvariantError(f"{label} property names must be Python identifiers and cannot be private or keywords.")
            normalized_properties[property_name] = _validate_schema(child, root_object=False, label=f"{label}.{property_name}", identifier_properties=identifier_properties)
        result["properties"] = normalized_properties
        result["required"] = list(required)
        result.setdefault("additionalProperties", False)
    elif schema_type == "array":
        result["items"] = _validate_schema(result.get("items"), root_object=False, label=f"{label}.items", identifier_properties=identifier_properties)
    return result


def _expression_function_row(item: Any) -> dict[str, Any]:
    return {
        "id": item.id,
        "name": item.name,
        "description": item.description,
        "parameterSchema": item.parameter_schema,
        "returnSchema": item.return_schema,
        "body": item.body,
        "language": item.language,
        "isBuiltin": item.is_builtin,
        "enabled": item.enabled,
        "createdAt": item.created_at,
        "updatedAt": item.updated_at,
        "createdBy": item.created_by,
        "updatedBy": item.updated_by,
    }


def _parameter_names(schema: Mapping[str, Any]) -> list[str]:
    return list(schema.get("properties", {}).keys()) if isinstance(schema.get("properties"), Mapping) else []


def _is_integrity_error(exc: Exception) -> bool:
    return "IntegrityError" in type(exc).__name__ or "unique" in str(exc).lower()
