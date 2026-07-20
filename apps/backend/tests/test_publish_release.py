from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

import pytest

from skillhub.services.publish_release import (
    PublishArtifact,
    perform_publish_release,
    publish_artifact_from_read_model,
)
from skillhub_worker.publish_runner import run_publish_once


class PublishStore:
    def __init__(self, artifact: dict[str, Any] | Exception):
        self.artifact = artifact
        self.completed: dict[str, Any] | None = None
        self.failed: dict[str, Any] | None = None
        self.heartbeats: list[dict[str, Any]] = []

    def claim_next_publish_release_job(self, *, worker_id: str) -> dict[str, Any]:
        return {
            "job": {"id": "job_1"},
            "record": {"id": "publish_1"},
            "execution": {"job_id": "job_1", "worker_id": worker_id, "attempt": 1},
            "release_payload": _release_payload(),
        }

    def publish_release_artifact(self, *, skill_version_id: str) -> dict[str, Any]:
        if isinstance(self.artifact, Exception):
            raise self.artifact
        return self.artifact

    def record_worker_heartbeat(self, **kwargs: Any) -> None:
        self.heartbeats.append(kwargs)

    def renew_job_lease(self, **kwargs: Any) -> bool:
        return True

    def complete_publish_release_job(self, **kwargs: Any) -> None:
        self.completed = kwargs

    def fail_publish_release_job(self, **kwargs: Any) -> None:
        self.failed = kwargs


def test_publish_artifact_dto_is_immutable_and_noop_reports_artifact():
    artifact = publish_artifact_from_read_model(_artifact_read_model())
    payload = _release_payload()
    payload["publish_target_key"] = "custom1"

    with pytest.raises(FrozenInstanceError):
        artifact.id = "changed"  # type: ignore[misc]

    result = perform_publish_release(payload, artifact, timeout_seconds=45)

    assert artifact.files[0].path == "SKILL.md"
    assert result["metadata"]["artifact_id"] == "artifact_1"
    assert result["metadata"]["artifact_digest"] == "digest"
    assert result["metadata"]["artifact_file_count"] == 1
    assert result["metadata"]["timeout_seconds"] == 45


def test_publish_worker_passes_artifact_to_release_hook(monkeypatch):
    store = PublishStore(_artifact_read_model())
    received: dict[str, Any] = {}

    def release(payload, artifact: PublishArtifact, *, timeout_seconds: float):
        received.update(payload=payload, artifact=artifact, timeout_seconds=timeout_seconds)
        return {"mode": "released", "external_id": "external_1"}

    monkeypatch.setattr("skillhub_worker.publish_runner.perform_publish_release", release)

    assert run_publish_once(store, config=_config()) is True
    assert received["payload"]["publish_record_id"] == "publish_1"
    assert received["artifact"].id == "artifact_1"
    assert received["artifact"].files[0].content_text == "content"
    assert received["timeout_seconds"] == 90
    assert store.completed is not None
    assert store.failed is None


def test_publish_worker_fails_without_calling_release_hook(monkeypatch):
    store = PublishStore(RuntimeError("SkillVersion has no skill_bundle artifact"))
    called = False

    def release(*args, **kwargs):
        nonlocal called
        called = True
        return {}

    monkeypatch.setattr("skillhub_worker.publish_runner.perform_publish_release", release)

    assert run_publish_once(store, config=_config()) is True
    assert called is False
    assert store.completed is None
    assert store.failed is not None
    assert store.failed["publish_record_id"] == "publish_1"
    assert store.failed["error"] == "SkillVersion has no skill_bundle artifact"


def _config():
    return SimpleNamespace(
        worker_id="publish-worker",
        publish_release_timeout_seconds=90,
        opencode_base_url="http://opencode.test",
        workdir_host="C:/tmp/skillhub",
        max_attempts=2,
    )


def _release_payload():
    return {
        "publish_record_id": "publish_1",
        "publish_target_id": "target_1",
        "publish_target_key": "yunxi",
        "publish_target_name": "云析",
        "publish_target_config": {},
        "skill_id": "skill_1",
        "skill_slug": "demo",
        "skill_tags": [],
        "skill_version_id": "version_1",
        "version": "1.0.0",
        "content_digest": "digest",
        "bundle_artifact_id": "artifact_1",
        "content_ref": {"kind": "artifact", "locator": "artifact:artifact_1", "digest": "digest"},
        "review_request_id": "review_1",
        "review_check_results": [],
        "requested_by": "maintainer",
        "confirmed_by": "publish-worker",
        "idempotency_key": "publish_release:publish_1",
    }


def _artifact_read_model():
    return {
        "id": "artifact_1",
        "kind": "skill_bundle",
        "namespace": "test:demo",
        "locator": "inline:digest",
        "digest": "digest",
        "media_type": "text/plain",
        "size_bytes": 7,
        "content_text": "manifest",
        "created_at": datetime(2026, 7, 20, tzinfo=timezone.utc),
        "created_by": "maintainer",
        "files": [
            {
                "path": "SKILL.md",
                "sha256": "file-digest",
                "size_bytes": 7,
                "binary": False,
                "content_text": "content",
                "content_base64": None,
            }
        ],
    }
