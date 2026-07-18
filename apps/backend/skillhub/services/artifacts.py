from __future__ import annotations

from base64 import b64decode
from dataclasses import dataclass

from skillhub.models.store import SkillHubStore
from skillhub.services.base import ServiceBase


@dataclass(frozen=True, slots=True)
class ArtifactDownload:
    filename: str
    content: bytes
    media_type: str


class ArtifactService(ServiceBase[SkillHubStore]):
    def bundle_diff(self, *, left_skill_version_id: str, right_skill_version_id: str) -> object:
        return self.store.bundle_diff(left_skill_version_id=left_skill_version_id, right_skill_version_id=right_skill_version_id)

    def downloadable_artifact(self, *, artifact_id: str) -> ArtifactDownload | None:
        artifact = self.store.downloadable_artifact(artifact_id)
        if artifact is None:
            return None
        filename = artifact["locator"].rsplit(":", 1)[-1] or "workspace.zip"
        return ArtifactDownload(filename=filename, content=b64decode(artifact["content_text"] or ""), media_type="application/zip")
