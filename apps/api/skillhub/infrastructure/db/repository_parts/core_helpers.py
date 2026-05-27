from __future__ import annotations

from datetime import datetime
import json
from typing import Any

from sqlalchemy import insert, select

from skillhub.domain.errors import FieldError, FieldInvariantError, InvariantError, NotFoundError
from skillhub.domain.models import ContentRef, digest_text, new_id
from skillhub.infrastructure.db import tables


class CoreHelperMixin:
    def _required_text(item: dict[str, Any], key: str) -> str:
        value = item.get(key)
        return value.strip() if isinstance(value, str) else ""

    def _normalize_eval_run_results(self, case_version_ids: list[str], results: dict[str, Any]) -> dict[str, dict[str, Any]]:
        expected_ids = set(case_version_ids)
        result_ids = set(results)
        field_errors = [
            FieldError(field=f"results.{case_version_id}", message="确认该测试用例通过或不通过。", code="eval_run.result_required")
            for case_version_id in case_version_ids
            if case_version_id not in result_ids
        ]
        field_errors.extend(
            FieldError(field=f"results.{case_version_id}", message="测试结果不属于当前 EvalSetVersion。", code="eval_run.result_unexpected")
            for case_version_id in sorted(result_ids - expected_ids)
        )
        if field_errors:
            raise FieldInvariantError("EvalRun results must exactly match the eval set version cases.", field_errors)
        normalized: dict[str, dict[str, Any]] = {}
        invalid_fields: list[FieldError] = []
        for case_version_id in case_version_ids:
            raw_result = results[case_version_id]
            if hasattr(raw_result, "model_dump"):
                raw_result = raw_result.model_dump()
            if isinstance(raw_result, bool):
                normalized[case_version_id] = {"passed": raw_result, "actual_output": ""}
                continue
            if isinstance(raw_result, dict) and isinstance(raw_result.get("passed"), bool):
                actual_output = raw_result.get("actual_output", "")
                if actual_output is None:
                    actual_output = ""
                if not isinstance(actual_output, str):
                    invalid_fields.append(
                        FieldError(
                            field=f"results.{case_version_id}.actual_output",
                            message="本次运行结果必须是文本。",
                            code="eval_run.actual_output_invalid",
                        )
                    )
                    continue
                normalized[case_version_id] = {"passed": raw_result["passed"], "actual_output": actual_output}
                continue
            invalid_fields.append(
                FieldError(field=f"results.{case_version_id}", message="确认该测试用例通过或不通过。", code="eval_run.result_invalid")
            )
        if invalid_fields:
            raise FieldInvariantError("EvalRun results must contain pass/fail values.", invalid_fields)
        return normalized

    def _skill_row(self, connection, skill_id: str):
        row = connection.execute(select(tables.skills).where(tables.skills.c.id == skill_id)).mappings().one_or_none()
        if row is None:
            raise NotFoundError(f"Skill not found: {skill_id}")
        return row

    def _skill_version_row(self, connection, version_id: str):
        row = connection.execute(select(tables.skill_versions).where(tables.skill_versions.c.id == version_id)).mappings().one_or_none()
        if row is None:
            raise NotFoundError(f"SkillVersion not found: {version_id}")
        return row

    def _eval_case_row(self, connection, case_id: str):
        row = connection.execute(select(tables.eval_cases).where(tables.eval_cases.c.id == case_id)).mappings().one_or_none()
        if row is None:
            raise NotFoundError(f"EvalCase not found: {case_id}")
        return row

    def _eval_case_version_row(self, connection, case_version_id: str):
        row = connection.execute(select(tables.eval_case_versions).where(tables.eval_case_versions.c.id == case_version_id)).mappings().one_or_none()
        if row is None:
            raise NotFoundError(f"EvalCaseVersion not found: {case_version_id}")
        return row

    def _primary_eval_set_row(self, connection, skill_id: str):
        row = (
            connection.execute(
                select(tables.eval_sets).where(tables.eval_sets.c.skill_id == skill_id).where(tables.eval_sets.c.name == "Primary")
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise NotFoundError(f"Primary EvalSet not found for skill: {skill_id}")
        return row

    def _eval_set_version_row(self, connection, eval_set_version_id: str):
        row = connection.execute(select(tables.eval_set_versions).where(tables.eval_set_versions.c.id == eval_set_version_id)).mappings().one_or_none()
        if row is None:
            raise NotFoundError(f"EvalSetVersion not found: {eval_set_version_id}")
        return row

    def _eval_run_row(self, connection, eval_run_id: str):
        row = connection.execute(select(tables.eval_runs).where(tables.eval_runs.c.id == eval_run_id)).mappings().one_or_none()
        if row is None:
            raise NotFoundError(f"EvalRun not found: {eval_run_id}")
        return row

    def _accepted_verification_row(self, connection, accepted_verification_id: str):
        row = (
            connection.execute(select(tables.accepted_verifications).where(tables.accepted_verifications.c.id == accepted_verification_id))
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise NotFoundError(f"AcceptedVerification not found: {accepted_verification_id}")
        return row

    def _accepted_verification_for_eval_run(self, connection, eval_run_id: str) -> dict[str, Any] | None:
        row = connection.execute(select(tables.accepted_verifications).where(tables.accepted_verifications.c.eval_run_id == eval_run_id)).mappings().one_or_none()
        return self._row_dict(row) if row is not None else None

    def _accepted_verification_for_context(
        self,
        connection,
        *,
        skill_id: str,
        skill_version_id: str,
        eval_set_version_id: str,
        run_context_hash: str,
    ) -> dict[str, Any] | None:
        row = (
            connection.execute(
                select(tables.accepted_verifications)
                .where(tables.accepted_verifications.c.skill_id == skill_id)
                .where(tables.accepted_verifications.c.skill_version_id == skill_version_id)
                .where(tables.accepted_verifications.c.eval_set_version_id == eval_set_version_id)
                .where(tables.accepted_verifications.c.run_context_hash == run_context_hash)
            )
            .mappings()
            .one_or_none()
        )
        return self._row_dict(row) if row is not None else None

    def _next_skill_version_number(self, connection, skill_id: str) -> int:
        return 1 + max(
            connection.execute(select(tables.skill_versions.c.version_number).where(tables.skill_versions.c.skill_id == skill_id)).scalars(),
            default=0,
        )

    def _next_eval_case_version_number(self, connection, case_id: str) -> int:
        return 1 + max(
            connection.execute(select(tables.eval_case_versions.c.version_number).where(tables.eval_case_versions.c.case_id == case_id)).scalars(),
            default=0,
        )

    def _next_eval_set_version_number(self, connection, eval_set_id: str) -> int:
        return 1 + max(
            connection.execute(select(tables.eval_set_versions.c.version_number).where(tables.eval_set_versions.c.eval_set_id == eval_set_id)).scalars(),
            default=0,
        )

    def _insert_text_artifact(
        self,
        connection,
        *,
        kind: str,
        namespace: str,
        content: str,
        actor: str,
        created_at: datetime,
    ) -> str:
        content_digest = digest_text(content)
        existing = (
            connection.execute(
                select(tables.artifacts.c.id)
                .where(tables.artifacts.c.locator == f"inline:{content_digest}")
                .where(tables.artifacts.c.digest == content_digest)
            )
            .scalars()
            .one_or_none()
        )
        if existing is not None:
            return existing
        artifact_id = new_id("artifact")
        connection.execute(
            insert(tables.artifacts).values(
                id=artifact_id,
                kind=kind,
                namespace=namespace,
                locator=f"inline:{content_digest}",
                digest=content_digest,
                media_type="text/plain",
                size_bytes=len(content.encode("utf-8")),
                content_text=content,
                created_at=created_at,
                created_by=actor,
            )
        )
        return artifact_id

    def _content_ref_payload(self, content_ref: ContentRef) -> dict[str, str]:
        payload = {"kind": content_ref.kind, "locator": content_ref.locator, "digest": content_ref.digest}
        if content_ref.path is not None:
            payload["path"] = content_ref.path
        return payload

    def _canonical_json_object(self, value: dict[str, Any]) -> dict[str, Any]:
        try:
            return json.loads(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        except (TypeError, ValueError) as exc:
            raise InvariantError("Run context must be JSON serializable.") from exc

    def _run_context_hash(self, tags: tuple[str, ...], context: dict[str, Any]) -> str:
        payload = {"environment_tags": list(tags), "run_context": context}
        return digest_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")))

    def _row_dict(self, row) -> dict[str, Any]:
        return dict(row)


def clean_display_name(value: str | None) -> str | None:
    if value is None:
        return None
    clean = value.strip()
    return clean or None
