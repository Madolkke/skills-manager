from __future__ import annotations

import json
from typing import Any

from skillhub.models.errors import InvariantError, NotFoundError
from skillhub.models.schema import orm


class BundleArtifactMixin:
    def publish_release_artifact(self, *, skill_version_id: str) -> dict[str, Any]:
        """Return a validated Skill Bundle artifact read model for release."""
        with self._read_session() as connection:
            version = self._skill_version_row(connection, skill_version_id)
            artifact, _files = self._bundle_artifact_for_version(connection, version)
            files = self._validated_bundle_files_from_artifact(artifact)
            content_ref = version["content_ref"] or {}
            expected_digest = version["content_digest"]
            if content_ref.get("digest") != expected_digest or artifact["digest"] != expected_digest:
                raise InvariantError(f"SkillVersion bundle artifact digest does not match: {skill_version_id}")
            return {**artifact, "files": files}

    def _bundle_artifact_for_version(self, connection, version) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        content_ref = version["content_ref"] or {}
        locator = content_ref.get("locator") if isinstance(content_ref, dict) else None
        if content_ref.get("kind") != "artifact" or not isinstance(locator, str) or not locator.startswith("artifact:"):
            raise InvariantError(f"SkillVersion has no skill_bundle artifact: {version['id']}")
        artifact_id = locator.split(":", 1)[1]
        if not artifact_id:
            raise InvariantError(f"SkillVersion has no skill_bundle artifact: {version['id']}")
        artifact = connection.execute(orm.select_entity(orm.Artifact).where(orm.Artifact.id == artifact_id)).mappings().one_or_none()
        if artifact is None:
            raise NotFoundError(f"Artifact not found: {artifact_id}")
        artifact_detail = self._row_dict(artifact)
        if artifact_detail["kind"] != "skill_bundle":
            raise InvariantError(f"SkillVersion artifact is not a skill_bundle: {version['id']}")
        files = self._bundle_files_from_artifact(artifact_detail)
        if not files:
            raise InvariantError(f"SkillVersion skill_bundle has no readable files: {version['id']}")
        return artifact_detail, files

    def _bundle_files_from_artifact(self, artifact: dict[str, Any]) -> list[dict[str, Any]]:
        content_text = artifact.get("content_text")
        if not isinstance(content_text, str):
            return []
        try:
            manifest = json.loads(content_text)
        except json.JSONDecodeError:
            return []
        files = manifest.get("files") if isinstance(manifest, dict) else None
        if not isinstance(files, list):
            return []
        return sorted([file for file in files if isinstance(file, dict) and isinstance(file.get("path"), str)], key=lambda file: file["path"])

    def _validated_bundle_files_from_artifact(self, artifact: dict[str, Any]) -> list[dict[str, Any]]:
        content_text = artifact.get("content_text")
        if not isinstance(content_text, str) or not content_text.strip():
            raise InvariantError(f"Skill Bundle artifact content is empty: {artifact['id']}")
        try:
            manifest = json.loads(content_text)
        except json.JSONDecodeError as exc:
            raise InvariantError(f"Skill Bundle artifact manifest is invalid JSON: {artifact['id']}") from exc
        raw_files = manifest.get("files") if isinstance(manifest, dict) else None
        if not isinstance(raw_files, list) or not raw_files:
            raise InvariantError(f"Skill Bundle artifact manifest has no files: {artifact['id']}")
        files = [self._validated_bundle_file(artifact["id"], file) for file in raw_files]
        paths = [file["path"] for file in files]
        if len(paths) != len(set(paths)):
            raise InvariantError(f"Skill Bundle artifact manifest has duplicate file paths: {artifact['id']}")
        return sorted(files, key=lambda file: file["path"])

    def _validated_bundle_file(self, artifact_id: str, value: Any) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise InvariantError(f"Skill Bundle artifact manifest contains an invalid file: {artifact_id}")
        path = value.get("path")
        digest = value.get("sha256")
        size_bytes = value.get("size_bytes")
        content_text = value.get("content_text")
        content_base64 = value.get("content_base64")
        has_text = isinstance(content_text, str)
        has_base64 = isinstance(content_base64, str)
        if (
            not isinstance(path, str)
            or not path.strip()
            or not isinstance(digest, str)
            or not digest
            or not isinstance(size_bytes, int)
            or isinstance(size_bytes, bool)
            or size_bytes < 0
            or has_text == has_base64
        ):
            raise InvariantError(f"Skill Bundle artifact manifest contains an invalid file: {artifact_id}")
        return {
            "path": path,
            "sha256": digest,
            "size_bytes": size_bytes,
            "binary": has_base64,
            "content_text": content_text if has_text else None,
            "content_base64": content_base64 if has_base64 else None,
        }
