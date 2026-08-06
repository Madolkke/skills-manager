from __future__ import annotations

from typing import Any

from skillhub.models.errors import FieldError, FieldInvariantError, InvariantError
from skillhub.models.rules.workflow_debug import validate_debug_case_target
from skillhub.services.workflow_debug_runtime import public_debug_case


class WorkflowDebugCaseServiceMixin:
    store: Any

    def list_cases(self, *, skill_id: str, actor: str, step_id: str | None = None) -> list[dict[str, Any]]:
        return [public_debug_case(item) for item in self.store.list_workflow_debug_cases(skill_id=skill_id, actor=actor, step_id=step_id)]

    def get_case(self, *, case_id: str, actor: str) -> dict[str, Any]:
        return public_debug_case(self.store.workflow_debug_case(case_id=case_id, actor=actor))

    def create_case(self, *, skill_id: str, values: dict[str, Any], actor: str) -> dict[str, Any]:
        document = self.store.workflow_debug_document(skill_id=skill_id, actor=actor)
        clean = _clean_case_values(values, partial=False)
        validate_debug_case_target(
            document,
            step_id=clean["step_id"],
            expected_target_id=clean["expected_target_id"],
        )
        return public_debug_case(self.store.insert_workflow_debug_case(skill_id=skill_id, values=clean, actor=actor))

    def update_case(self, *, case_id: str, values: dict[str, Any], actor: str) -> dict[str, Any]:
        current = self.store.workflow_debug_case(case_id=case_id, actor=actor)
        clean = _clean_case_values(values, partial=True)
        if "expected_target_id" in clean:
            document = self.store.workflow_debug_document(skill_id=current["skill_id"], actor=actor)
            validate_debug_case_target(
                document,
                step_id=current["step_id"],
                expected_target_id=clean["expected_target_id"],
            )
        return public_debug_case(self.store.update_workflow_debug_case(case_id=case_id, values=clean, actor=actor))

    def delete_case(self, *, case_id: str, actor: str) -> dict[str, bool]:
        return self.store.delete_workflow_debug_case(case_id=case_id, actor=actor)


def _clean_case_values(values: dict[str, Any], *, partial: bool) -> dict[str, Any]:
    if partial and not values:
        raise InvariantError("Workflow debug case update must include at least one field.")
    errors: list[FieldError] = []
    clean = dict(values)
    for key in ("name", "description", "expected_target_id"):
        if key not in clean:
            continue
        value = clean[key]
        if value is None:
            errors.append(FieldError(field=key, message="字段不能为 null。", code="workflow_debug.null_field"))
            continue
        clean[key] = value.strip() if key != "description" else value
    if "name" in clean and not clean["name"]:
        errors.append(FieldError(field="name", message="请填写调试例名称。", code="workflow_debug.name_required"))
    for key in ("workflow_inputs", "collection_fixtures"):
        if key in clean and clean[key] is None:
            errors.append(FieldError(field=key, message="字段不能为 null。", code="workflow_debug.null_field"))
    if errors:
        raise FieldInvariantError("Workflow 调试例字段不正确。", errors)
    return clean


__all__ = ["WorkflowDebugCaseServiceMixin"]
