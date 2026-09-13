from __future__ import annotations

from typing import Any

from skillhub.models.store import SkillHubStore
from skillhub.services.base import ServiceBase


class ExpressionFunctionService(ServiceBase[SkillHubStore]):
    """Manage global expression metadata without exposing executable function bodies."""

    def list_functions(self) -> list[dict[str, Any]]:
        return self.store.list_expression_functions()

    def get_function(self, *, function_id: str) -> dict[str, Any]:
        return self.store.get_expression_function(function_id=function_id)

    def create_function(self, *, payload: dict[str, Any], actor: str) -> dict[str, Any]:
        return self.store.create_expression_function(payload=payload, actor=actor)

    def update_function(self, *, function_id: str, payload: dict[str, Any], actor: str) -> dict[str, Any]:
        return self.store.update_expression_function(function_id=function_id, payload=payload, actor=actor)

    def delete_function(self, *, function_id: str) -> dict[str, Any]:
        return self.store.delete_expression_function(function_id=function_id)
