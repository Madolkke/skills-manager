from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, TypedDict

from skillhub.services.yunxi_release import publish_to_yunxi


class PublishSkillTag(TypedDict):
    group_id: str
    value: str


class PublishReleasePayload(TypedDict):
    publish_record_id: str
    publish_target_id: str
    publish_target_key: str
    publish_target_name: str
    publish_target_config: dict[str, Any]
    skill_id: str
    skill_slug: str
    skill_tags: list[PublishSkillTag]
    skill_version_id: str
    version: str
    content_digest: str
    bundle_artifact_id: str | None
    content_ref: dict[str, Any]
    review_request_id: str
    review_check_results: list[dict[str, Any]]
    requested_by: str
    confirmed_by: str
    idempotency_key: str


class PublishReleaseResult(TypedDict, total=False):
    mode: str
    external_id: str
    message: str
    metadata: dict[str, Any]


@dataclass(frozen=True, slots=True)
class PublishArtifactFile:
    path: str
    sha256: str
    size_bytes: int
    binary: bool
    content_text: str | None
    content_base64: str | None


@dataclass(frozen=True, slots=True)
class PublishArtifact:
    id: str
    kind: str
    namespace: str
    locator: str
    digest: str
    media_type: str
    size_bytes: int
    content_text: str
    created_at: datetime
    created_by: str
    files: tuple[PublishArtifactFile, ...]


def publish_artifact_from_read_model(value: Mapping[str, Any]) -> PublishArtifact:
    return PublishArtifact(
        id=str(value["id"]),
        kind=str(value["kind"]),
        namespace=str(value["namespace"]),
        locator=str(value["locator"]),
        digest=str(value["digest"]),
        media_type=str(value["media_type"]),
        size_bytes=int(value["size_bytes"]),
        content_text=str(value["content_text"]),
        created_at=value["created_at"],
        created_by=str(value["created_by"]),
        files=tuple(
            PublishArtifactFile(
                path=str(file["path"]),
                sha256=str(file["sha256"]),
                size_bytes=int(file["size_bytes"]),
                binary=bool(file["binary"]),
                content_text=file.get("content_text"),
                content_base64=file.get("content_base64"),
            )
            for file in value["files"]
        ),
    )


def perform_publish_release(
    payload: PublishReleasePayload,
    artifact: PublishArtifact,
    *,
    timeout_seconds: float = 120,
) -> PublishReleaseResult:
    """Hook for integrating real publish behavior."""

    if payload["publish_target_key"] == "yunxi":
        required_tag: PublishSkillTag = {"group_id": "A", "value": "a"}
        if required_tag not in payload["skill_tags"]:
            return {
                "mode": "skipped",
                "message": "Skill does not have the tag required by the Yunxi publish source.",
                "metadata": {
                    "reason": "required_tag_missing",
                    "required_tag": required_tag,
                    "artifact_id": artifact.id,
                    "artifact_digest": artifact.digest,
                },
            }
        root = Path("/var/lib/skillhub/publish/yunxi")
        return publish_to_yunxi(payload, artifact, root=root, timeout_seconds=timeout_seconds)

    return {
        "mode": "noop",
        "message": "Release hook is not configured.",
        "metadata": {
            "publish_record_id": payload["publish_record_id"],
            "publish_target_key": payload["publish_target_key"],
            "skill_version_id": payload["skill_version_id"],
            "idempotency_key": payload["idempotency_key"],
            "timeout_seconds": timeout_seconds,
            "artifact_id": artifact.id,
            "artifact_digest": artifact.digest,
            "artifact_file_count": len(artifact.files),
        },
    }
