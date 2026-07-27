from __future__ import annotations

from typing import Any

from skillhub.models.rules.bundle_diffs import build_bundle_file_diff, line_diff_hunks


class BundleDiffMixin:
    def _bundle_diff_from_versions(self, connection, left_version, right_version) -> dict[str, Any]:
        """Compare the validated Bundle files attached to two SkillVersions."""
        _left_artifact, left_files = self._bundle_artifact_for_version(connection, left_version)
        _right_artifact, right_files = self._bundle_artifact_for_version(connection, right_version)
        diff = build_bundle_file_diff(left_files, right_files)
        return {
            "left": self._diff_version_summary(left_version),
            "right": self._diff_version_summary(right_version),
            **diff,
        }

    def _diff_version_summary(self, version) -> dict[str, Any]:
        """Project a SkillVersion into the compact Bundle diff identity shape."""
        return {
            "skill_version_id": version["id"],
            "version_number": version["version_number"],
            "version": version["version"],
            "content_digest": version["content_digest"],
        }

    def _line_diff_hunks(self, left_text: str | None, right_text: str | None) -> list[dict[str, Any]]:
        """Keep the historical helper surface while delegating to the shared rule."""
        return line_diff_hunks(left_text, right_text)
