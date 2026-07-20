from __future__ import annotations

import base64
import hashlib
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import pytest
from filelock import FileLock

import skillhub.services.publish_release as release_module
import skillhub.services.yunxi_release as yunxi_module
from skillhub.services.publish_release import PublishArtifact, PublishArtifactFile, perform_publish_release
from skillhub.services.yunxi_release import publish_to_yunxi

YUNXI_ROOT = "/var/lib/skillhub/publish/yunxi"


def test_yunxi_release_writes_text_and_binary_bundle(monkeypatch, tmp_path: Path):
    root = _patch_yunxi_root(monkeypatch, tmp_path)
    artifact = _artifact(
        "digest-1",
        _text_file("SKILL.md", "---\nname: demo\n---\n"),
        _binary_file("references/data.bin", b"\x00\x01"),
    )

    result = perform_publish_release(_payload(), artifact, timeout_seconds=5)

    target = root / "demo"
    assert result["mode"] == "filesystem"
    assert result["external_id"] == str(target)
    assert (target / "SKILL.md").read_text(encoding="utf-8") == "---\nname: demo\n---\n"
    assert (target / "references/data.bin").read_bytes() == b"\x00\x01"
    assert result["metadata"]["file_count"] == 2
    assert result["metadata"]["required_tag"] == {"group_id": "A", "value": "a"}


@pytest.mark.parametrize(
    "tags",
    [
        [],
        [{"group_id": "A", "value": "A"}],
        [{"group_id": "other", "value": "a", "group_display_name": "A", "value_display_name": "a"}],
    ],
)
def test_yunxi_release_skips_when_internal_tag_does_not_match(monkeypatch, tmp_path: Path, tags):
    root = _patch_yunxi_root(monkeypatch, tmp_path)
    payload = _payload()
    payload["skill_tags"] = tags

    result = perform_publish_release(payload, _artifact("digest", _text_file("SKILL.md", "content")))

    assert result["mode"] == "skipped"
    assert result["metadata"]["reason"] == "required_tag_missing"
    assert not root.exists()


def test_yunxi_release_is_idempotent_and_repairs_missing_state(monkeypatch, tmp_path: Path):
    root = _patch_yunxi_root(monkeypatch, tmp_path)
    payload = _payload()
    artifact = _artifact("digest", _text_file("SKILL.md", "content"))

    first = perform_publish_release(payload, artifact)
    state_path = root.parent / ".yunxi-control/state/demo.json"
    state_path.unlink()
    second = perform_publish_release(payload, artifact)

    assert first["mode"] == "filesystem"
    assert second["mode"] == "already_current"
    assert second["metadata"]["state_recovered"] is True
    assert state_path.exists()


def test_yunxi_release_replaces_whole_skill_directory(monkeypatch, tmp_path: Path):
    root = _patch_yunxi_root(monkeypatch, tmp_path)
    first = _artifact("digest-1", _text_file("SKILL.md", "first"), _text_file("old.md", "old"))
    second = _artifact("digest-2", _text_file("SKILL.md", "second"), _text_file("new.md", "new"))

    perform_publish_release(_payload(), first)
    result = perform_publish_release(_payload(record_id="publish_2", version="2.0.0"), second)

    target = root / "demo"
    assert result["mode"] == "filesystem"
    assert (target / "SKILL.md").read_text(encoding="utf-8") == "second"
    assert (target / "new.md").exists()
    assert not (target / "old.md").exists()


@pytest.mark.parametrize(
    ("file", "message"),
    [
        (PublishArtifactFile("../escape", hashlib.sha256(b"x").hexdigest(), 1, False, "x", None), "unsafe file path"),
        (PublishArtifactFile("data.bin", "digest", 1, True, None, "not-base64"), "not valid base64"),
        (PublishArtifactFile("SKILL.md", hashlib.sha256(b"x").hexdigest(), 2, False, "x", None), "size does not match"),
        (PublishArtifactFile("SKILL.md", "wrong", 1, False, "x", None), "digest does not match"),
    ],
)
def test_yunxi_release_rejects_invalid_bundle_files(tmp_path: Path, file: PublishArtifactFile, message: str):
    with pytest.raises(RuntimeError, match=message):
        publish_to_yunxi(_payload(), _artifact("digest", file), root=tmp_path / "yunxi", timeout_seconds=1)


def test_yunxi_release_lock_timeout_fails(tmp_path: Path):
    root = tmp_path / "yunxi"
    lock_path = root.parent / ".yunxi-control/locks/demo.lock"
    lock_path.parent.mkdir(parents=True)
    artifact = _artifact("digest", _text_file("SKILL.md", "content"))

    with FileLock(str(lock_path)):
        with pytest.raises(RuntimeError, match="Timed out waiting for Yunxi publish lock"):
            publish_to_yunxi(_payload(), artifact, root=root, timeout_seconds=0.01)


def test_yunxi_release_propagates_filesystem_permission_error(monkeypatch, tmp_path: Path):
    artifact = _artifact("digest", _text_file("SKILL.md", "content"))

    def deny_write(staging: Path, value: PublishArtifact) -> None:
        raise PermissionError("publish directory is read-only")

    monkeypatch.setattr(yunxi_module, "_write_bundle", deny_write)

    with pytest.raises(PermissionError, match="publish directory is read-only"):
        publish_to_yunxi(_payload(), artifact, root=tmp_path / "yunxi", timeout_seconds=1)


def test_concurrent_yunxi_releases_do_not_mix_files(tmp_path: Path):
    root = tmp_path / "yunxi"
    artifact = _artifact("digest", _text_file("SKILL.md", "content"), _text_file("references/check.md", "check"))
    payloads = [_payload(record_id=f"publish_{index}") for index in range(2)]

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda payload: publish_to_yunxi(payload, artifact, root=root, timeout_seconds=5), payloads))

    assert {result["mode"] for result in results} == {"filesystem", "already_current"}
    assert (root / "demo/SKILL.md").read_text(encoding="utf-8") == "content"
    assert (root / "demo/references/check.md").read_text(encoding="utf-8") == "check"


def test_other_publish_target_remains_noop(tmp_path: Path):
    payload = _payload()
    payload["publish_target_key"] = "custom1"

    result = perform_publish_release(payload, _artifact("digest", _text_file("SKILL.md", "content")))

    assert result["mode"] == "noop"


def _patch_yunxi_root(monkeypatch, tmp_path: Path) -> Path:
    root = tmp_path / "yunxi"
    real_path = Path
    monkeypatch.setattr(release_module, "Path", lambda value: root if value == YUNXI_ROOT else real_path(value))
    return root


def _payload(*, record_id: str = "publish_1", version: str = "1.0.0"):
    return {
        "publish_record_id": record_id,
        "publish_target_id": "target_yunxi",
        "publish_target_key": "yunxi",
        "publish_target_name": "云析",
        "publish_target_config": {},
        "skill_id": "skill_1",
        "skill_slug": "demo",
        "skill_tags": [{"group_id": "A", "value": "a"}],
        "skill_version_id": "version_1",
        "version": version,
        "content_digest": "digest",
        "bundle_artifact_id": "artifact_1",
        "content_ref": {"kind": "artifact", "locator": "artifact:artifact_1", "digest": "digest"},
        "review_request_id": "review_1",
        "review_check_results": [],
        "requested_by": "maintainer",
        "confirmed_by": "publish-worker",
        "idempotency_key": f"publish_release:{record_id}",
    }


def _artifact(digest: str, *files: PublishArtifactFile) -> PublishArtifact:
    return PublishArtifact(
        id="artifact_1",
        kind="skill_bundle",
        namespace="test:demo",
        locator=f"inline:{digest}",
        digest=digest,
        media_type="text/plain",
        size_bytes=sum(file.size_bytes for file in files),
        content_text="manifest",
        created_at=datetime(2026, 7, 21, tzinfo=timezone.utc),
        created_by="maintainer",
        files=files,
    )


def _text_file(path: str, content: str) -> PublishArtifactFile:
    raw = content.encode("utf-8")
    return PublishArtifactFile(path, hashlib.sha256(raw).hexdigest(), len(raw), False, content, None)


def _binary_file(path: str, content: bytes) -> PublishArtifactFile:
    return PublishArtifactFile(
        path,
        hashlib.sha256(content).hexdigest(),
        len(content),
        True,
        None,
        base64.b64encode(content).decode("ascii"),
    )
