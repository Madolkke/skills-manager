from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import shutil
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING

from filelock import FileLock, Timeout

if TYPE_CHECKING:
    from skillhub.services.publish_release import PublishArtifact, PublishArtifactFile, PublishReleasePayload, PublishReleaseResult

SKILL_SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
REQUIRED_TAG = {"group_id": "A", "value": "a"}


def publish_to_yunxi(
    payload: PublishReleasePayload,
    artifact: PublishArtifact,
    *,
    root: Path,
    timeout_seconds: float,
) -> PublishReleaseResult:
    """Materialize a validated Skill Bundle into the Yunxi source directory."""
    slug = payload["skill_slug"]
    if not SKILL_SLUG_PATTERN.fullmatch(slug):
        raise RuntimeError(f"Yunxi publish requires a safe Skill slug: {slug}")

    control_root = root.parent / ".yunxi-control"
    staging_root = control_root / "staging"
    state_root = control_root / "state"
    lock_root = control_root / "locks"
    for directory in (root, staging_root, state_root, lock_root):
        directory.mkdir(parents=True, exist_ok=True)

    target = root / slug
    staging = staging_root / f"{slug}-{payload['publish_record_id']}"
    backup = staging_root / f"{slug}-backup"
    state_path = state_root / f"{slug}.json"
    lock = FileLock(str(lock_root / f"{slug}.lock"), timeout=max(0, timeout_seconds))
    try:
        with lock:
            _recover_backup(target, backup)
            state = _read_state(state_path)
            if _directory_matches(target, artifact):
                _write_state(state_path, payload, artifact, target)
                return _result(
                    "already_current",
                    payload,
                    artifact,
                    target,
                    state_recovered=not _state_matches(state, payload, artifact),
                )

            _remove_path(staging)
            staging.mkdir(parents=True)
            try:
                _write_bundle(staging, artifact)
                _replace_directory(staging, target, backup)
                _write_state(state_path, payload, artifact, target)
            finally:
                _remove_path(staging)
            return _result("filesystem", payload, artifact, target)
    except Timeout as exc:
        raise RuntimeError(f"Timed out waiting for Yunxi publish lock: {slug}") from exc


def _write_bundle(staging: Path, artifact: PublishArtifact) -> None:
    seen: set[str] = set()
    for file in artifact.files:
        relative = _safe_relative_path(file.path)
        if relative.as_posix() in seen:
            raise RuntimeError(f"Skill Bundle contains duplicate file path: {file.path}")
        seen.add(relative.as_posix())
        content = _file_bytes(file)
        target = staging.joinpath(*relative.parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)


def _safe_relative_path(value: str) -> PurePosixPath:
    candidate = PurePosixPath(value)
    if (
        not value
        or "\\" in value
        or candidate.is_absolute()
        or candidate.as_posix() != value
        or any(part in {"", ".", ".."} for part in candidate.parts)
    ):
        raise RuntimeError(f"Skill Bundle contains an unsafe file path: {value}")
    return candidate


def _file_bytes(file: PublishArtifactFile) -> bytes:
    if file.binary:
        if file.content_text is not None or file.content_base64 is None:
            raise RuntimeError(f"Binary Skill Bundle file has invalid content: {file.path}")
        try:
            content = base64.b64decode(file.content_base64, validate=True)
        except ValueError as exc:
            raise RuntimeError(f"Binary Skill Bundle file is not valid base64: {file.path}") from exc
    else:
        if file.content_text is None or file.content_base64 is not None:
            raise RuntimeError(f"Text Skill Bundle file has invalid content: {file.path}")
        content = file.content_text.encode("utf-8")
    if len(content) != file.size_bytes:
        raise RuntimeError(f"Skill Bundle file size does not match manifest: {file.path}")
    if hashlib.sha256(content).hexdigest() != file.sha256:
        raise RuntimeError(f"Skill Bundle file digest does not match manifest: {file.path}")
    return content


def _directory_matches(target: Path, artifact: PublishArtifact) -> bool:
    if not target.is_dir() or target.is_symlink():
        return False
    expected = {file.path: file for file in artifact.files}
    actual: dict[str, Path] = {}
    for path in target.rglob("*"):
        if path.is_symlink():
            return False
        if path.is_file():
            actual[path.relative_to(target).as_posix()] = path
    if set(actual) != set(expected):
        return False
    for relative, file in expected.items():
        try:
            content = actual[relative].read_bytes()
        except OSError:
            return False
        if len(content) != file.size_bytes or hashlib.sha256(content).hexdigest() != file.sha256:
            return False
    return True


def _recover_backup(target: Path, backup: Path) -> None:
    if _path_exists(target):
        _remove_path(backup)
    elif _path_exists(backup):
        backup.rename(target)


def _replace_directory(staging: Path, target: Path, backup: Path) -> None:
    _remove_path(backup)
    if _path_exists(target):
        target.rename(backup)
    try:
        staging.rename(target)
    except Exception:
        if not _path_exists(target) and _path_exists(backup):
            backup.rename(target)
        raise
    _remove_path(backup)


def _path_exists(path: Path) -> bool:
    return path.exists() or path.is_symlink()


def _remove_path(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink(missing_ok=True)
    elif path.is_dir():
        shutil.rmtree(path)


def _read_state(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _state_matches(state: dict, payload: PublishReleasePayload, artifact: PublishArtifact) -> bool:
    return state.get("idempotency_key") == payload["idempotency_key"] and state.get("artifact_digest") == artifact.digest


def _write_state(path: Path, payload: PublishReleasePayload, artifact: PublishArtifact, target: Path) -> None:
    value = {
        "idempotency_key": payload["idempotency_key"],
        "publish_record_id": payload["publish_record_id"],
        "skill_slug": payload["skill_slug"],
        "version": payload["version"],
        "artifact_digest": artifact.digest,
        "target_path": str(target),
    }
    temporary = path.with_suffix(f".{payload['publish_record_id']}.tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _result(
    mode: str,
    payload: PublishReleasePayload,
    artifact: PublishArtifact,
    target: Path,
    *,
    state_recovered: bool = False,
) -> PublishReleaseResult:
    return {
        "mode": mode,
        "external_id": str(target),
        "message": "Skill Bundle written to Yunxi publish source." if mode == "filesystem" else "Yunxi publish source is already current.",
        "metadata": {
            "artifact_digest": artifact.digest,
            "file_count": len(artifact.files),
            "size_bytes": sum(file.size_bytes for file in artifact.files),
            "required_tag": REQUIRED_TAG,
            "state_recovered": state_recovered,
        },
    }
