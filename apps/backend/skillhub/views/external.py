from __future__ import annotations

import json

from fastapi import Depends, FastAPI, File, Form, UploadFile
from pydantic import ValidationError

from skillhub.models.errors import FieldError, FieldInvariantError
from skillhub.services import ExternalSkillService
from skillhub.views.dependencies import external_skill_service_dependency
from skillhub.views.responses import result_payload
from skillhub.views.schemas import ExternalSkillUpsertTagsPayload, IdentityRef, SkillVersionSemVer, VersionChangeSummary, VersionDisplayName


def register_external_routes(app: FastAPI) -> None:
    @app.post("/api/external/skills/upsert-zip")
    async def upsert_skill_zip(
        actor_id: IdentityRef = Form(...),
        tags: str = Form(...),
        file: UploadFile = File(...),
        display_name: VersionDisplayName | None = Form(default=None),
        version: SkillVersionSemVer | None = Form(default=None),
        change_summary: VersionChangeSummary | None = Form(default=None),
        make_current: bool = Form(default=True),
        service: ExternalSkillService = Depends(external_skill_service_dependency),
    ):
        archive = await file.read()
        parsed_tags = _parse_tags_form(tags)
        return result_payload(
            service.upsert_skill_bundle_for_owner(
                owner_ref=actor_id,
                archive=archive,
                actor=actor_id,
                tags=parsed_tags,
                change_summary=change_summary,
                display_name=display_name,
                version=version,
                make_current=make_current,
            )
        )


def _parse_tags_form(value: str) -> list[dict[str, str]]:
    try:
        raw_tags = json.loads(value)
        payload = ExternalSkillUpsertTagsPayload(tags=raw_tags)
    except (json.JSONDecodeError, ValidationError) as exc:
        raise FieldInvariantError(
            "External skill upsert tags are invalid.",
            [FieldError(field="tags", message="tags 必须是有效的 Tag 数组 JSON。", code="external_skill.tags_invalid")],
        ) from exc
    return [{"group_id": tag.group_id, "value": tag.value} for tag in payload.tags]
