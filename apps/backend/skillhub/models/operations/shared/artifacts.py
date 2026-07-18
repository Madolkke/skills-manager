from __future__ import annotations

from typing import Any

from skillhub.models.schema import orm


class ArtifactQueryMixin:
    def downloadable_artifact(self, artifact_id: str) -> dict[str, Any] | None:
        with self._read_session() as connection:
            artifact = connection.execute(orm.select_entity(orm.Artifact).where(orm.Artifact.id == artifact_id)).mappings().one_or_none()
        if artifact is None or artifact["kind"] not in {"eval_case_attachment", "eval_case_workspace"} or artifact["media_type"] != "application/zip":
            return None
        return self._row_dict(artifact)
