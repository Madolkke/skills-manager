from __future__ import annotations

from typing import Any, TypedDict


class PublishReleasePayload(TypedDict):
    publish_record_id: str
    publish_target_id: str
    publish_target_key: str
    publish_target_name: str
    publish_target_config: dict[str, Any]
    skill_id: str
    skill_slug: str
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


def perform_publish_release(payload: PublishReleasePayload, *, timeout_seconds: float = 120) -> PublishReleaseResult:
    """Hook for integrating real publish behavior."""

    return {
        "mode": "noop",
        "message": "Release hook is not configured.",
        "metadata": {
            "publish_record_id": payload["publish_record_id"],
            "publish_target_key": payload["publish_target_key"],
            "skill_version_id": payload["skill_version_id"],
            "idempotency_key": payload["idempotency_key"],
            "timeout_seconds": timeout_seconds,
        },
    }
