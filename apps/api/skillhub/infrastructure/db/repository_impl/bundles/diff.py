from __future__ import annotations

from difflib import SequenceMatcher
import json
from typing import Any

from sqlalchemy import select

from skillhub.domain.errors import InvariantError, NotFoundError
from skillhub.infrastructure.db import tables


class BundleDiffMixin:
    def _bundle_diff_from_versions(self, connection, left_version, right_version) -> dict[str, Any]:
        _left_artifact, left_files = self._bundle_artifact_for_version(connection, left_version)
        _right_artifact, right_files = self._bundle_artifact_for_version(connection, right_version)
        left_by_path = {file["path"]: file for file in left_files}
        right_by_path = {file["path"]: file for file in right_files}
        summary = {"added": 0, "removed": 0, "changed": 0, "unchanged": 0, "binary": 0}
        files = []
        for path in sorted(set(left_by_path) | set(right_by_path)):
            left_file = left_by_path.get(path)
            right_file = right_by_path.get(path)
            if left_file is None:
                status = "added"
            elif right_file is None:
                status = "removed"
            elif left_file.get("sha256") == right_file.get("sha256"):
                status = "unchanged"
            else:
                status = "changed"
            summary[status] += 1
            if status == "unchanged":
                continue
            binary = bool((left_file or {}).get("binary") or (right_file or {}).get("binary"))
            if binary:
                summary["binary"] += 1
            diff_file = {
                "path": path,
                "status": status,
                "binary": binary,
                "left_digest": left_file.get("sha256") if left_file else None,
                "right_digest": right_file.get("sha256") if right_file else None,
                "left_size_bytes": left_file.get("size_bytes") if left_file else None,
                "right_size_bytes": right_file.get("size_bytes") if right_file else None,
            }
            left_text = left_file.get("content_text") if left_file else None
            right_text = right_file.get("content_text") if right_file else None
            if not binary and (left_text is None or isinstance(left_text, str)) and (right_text is None or isinstance(right_text, str)):
                diff_file["hunks"] = self._line_diff_hunks(left_text, right_text)
            files.append(diff_file)
        return {
            "left": self._diff_version_summary(left_version),
            "right": self._diff_version_summary(right_version),
            "summary": summary,
            "files": files,
        }

    def _bundle_artifact_for_version(self, connection, version) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        content_ref = version["content_ref"] or {}
        locator = content_ref.get("locator") if isinstance(content_ref, dict) else None
        if content_ref.get("kind") != "artifact" or not isinstance(locator, str) or not locator.startswith("artifact:"):
            raise InvariantError(f"SkillVersion has no skill_bundle artifact to diff: {version['id']}")
        artifact_id = locator.split(":", 1)[1]
        artifact = connection.execute(select(tables.artifacts).where(tables.artifacts.c.id == artifact_id)).mappings().one_or_none()
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

    def _diff_version_summary(self, version) -> dict[str, Any]:
        return {
            "skill_version_id": version["id"],
            "version_number": version["version_number"],
            "version": version["version"],
            "content_digest": version["content_digest"],
        }

    def _line_diff_hunks(self, left_text: str | None, right_text: str | None) -> list[dict[str, Any]]:
        left_lines = [] if left_text is None else left_text.splitlines()
        right_lines = [] if right_text is None else right_text.splitlines()
        lines = []
        matcher = SequenceMatcher(a=left_lines, b=right_lines)
        for tag, left_start, left_end, right_start, right_end in matcher.get_opcodes():
            if tag == "equal":
                for offset, text in enumerate(left_lines[left_start:left_end]):
                    lines.append({"kind": "context", "old_line": left_start + offset + 1, "new_line": right_start + offset + 1, "text": text})
            if tag in {"delete", "replace"}:
                for offset, text in enumerate(left_lines[left_start:left_end]):
                    lines.append({"kind": "removed", "old_line": left_start + offset + 1, "new_line": None, "text": text})
            if tag in {"insert", "replace"}:
                for offset, text in enumerate(right_lines[right_start:right_end]):
                    lines.append({"kind": "added", "old_line": None, "new_line": right_start + offset + 1, "text": text})
        if not lines:
            return []
        return [{"old_start": 1 if left_lines else 0, "old_lines": len(left_lines), "new_start": 1 if right_lines else 0, "new_lines": len(right_lines), "lines": lines}]
