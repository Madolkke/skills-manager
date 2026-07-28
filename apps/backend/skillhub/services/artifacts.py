from __future__ import annotations

from base64 import b64decode
from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from pathlib import Path, PurePosixPath
from shutil import rmtree
from zipfile import ZIP_DEFLATED, ZipFile

from skillhub.models.errors import InvariantError
from skillhub.models.store import SkillHubStore
from skillhub.services.base import ServiceBase

QUICK_PUBLISH_DIRECTORY = Path(r"D:\workspace\skills-manager\.data\quick-published-skills")


@dataclass(frozen=True, slots=True)
class ArtifactDownload:
    filename: str
    content: bytes
    media_type: str


@dataclass(frozen=True, slots=True)
class QuickPublishResult:
    destination: str
    file_count: int


class ArtifactService(ServiceBase[SkillHubStore]):
    def bundle_diff(self, *, left_skill_version_id: str, right_skill_version_id: str) -> object:
        return self.store.bundle_diff(left_skill_version_id=left_skill_version_id, right_skill_version_id=right_skill_version_id)

    def downloadable_artifact(self, *, artifact_id: str) -> ArtifactDownload | None:
        artifact = self.store.downloadable_artifact(artifact_id)
        if artifact is None:
            return None
        filename = artifact["locator"].rsplit(":", 1)[-1] or "workspace.zip"
        return ArtifactDownload(filename=filename, content=b64decode(artifact["content_text"] or ""), media_type="application/zip")

    def downloadable_skill_bundle(self, *, skill_version_id: str, actor: str) -> ArtifactDownload:
        """Create a ZIP archive for one permission-checked immutable Skill version."""
        artifact = self.store.publish_release_artifact(skill_version_id=skill_version_id, actor=actor)
        return ArtifactDownload(
            filename=f"skill-{skill_version_id}.zip",
            content=self._bundle_zip(artifact["files"]),
            media_type="application/zip",
        )

    def quick_publish_skill_bundle(self, *, skill_version_id: str, actor: str) -> QuickPublishResult:
        """Write one immutable Skill Bundle into the fixed local publish directory."""
        artifact = self.store.publish_release_artifact(skill_version_id=skill_version_id, actor=actor)
        destination = QUICK_PUBLISH_DIRECTORY / skill_version_id
        temporary_destination = QUICK_PUBLISH_DIRECTORY / f".{skill_version_id}.tmp"
        if temporary_destination.exists():
            rmtree(temporary_destination)
        temporary_destination.mkdir(parents=True)
        try:
            self._write_bundle(temporary_destination, artifact["files"])
            if destination.exists():
                rmtree(destination)
            temporary_destination.replace(destination)
        except Exception:
            if temporary_destination.exists():
                rmtree(temporary_destination)
            raise
        return QuickPublishResult(destination=str(destination), file_count=len(artifact["files"]))

    def _bundle_zip(self, files: list[dict[str, object]]) -> bytes:
        archive = BytesIO()
        with ZipFile(archive, "w", compression=ZIP_DEFLATED) as zip_file:
            for file in files:
                zip_file.writestr(self._bundle_relative_path(file), self._bundle_file_content(file))
        return archive.getvalue()

    def _write_bundle(self, destination: Path, files: list[dict[str, object]]) -> None:
        for file in files:
            relative_path = self._bundle_relative_path(file)
            output_path = destination.joinpath(*PurePosixPath(relative_path).parts)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(self._bundle_file_content(file))

    def _bundle_relative_path(self, file: dict[str, object]) -> str:
        path = file.get("path")
        if not isinstance(path, str):
            raise InvariantError("Skill Bundle contains an invalid file path.")
        pure_path = PurePosixPath(path)
        if pure_path.is_absolute() or "\\" in path or any(part in {"", ".", ".."} for part in pure_path.parts):
            raise InvariantError(f"Skill Bundle contains an unsafe file path: {path}")
        return path

    def _bundle_file_content(self, file: dict[str, object]) -> bytes:
        content_text = file.get("content_text")
        content_base64 = file.get("content_base64")
        if isinstance(content_text, str):
            content = content_text.encode("utf-8")
        elif isinstance(content_base64, str):
            try:
                content = b64decode(content_base64, validate=True)
            except ValueError as exc:
                raise InvariantError("Skill Bundle contains invalid binary file content.") from exc
        else:
            raise InvariantError("Skill Bundle contains unreadable file content.")
        expected_size = file.get("size_bytes")
        expected_digest = file.get("sha256")
        if expected_size != len(content) or expected_digest != sha256(content).hexdigest():
            raise InvariantError("Skill Bundle file content does not match its manifest.")
        return content
