from __future__ import annotations

from typing import Any

from sqlalchemy import select

from skillhub.models.schema import tables


class ArtifactQueryMixin:
    def downloadable_artifact(self, artifact_id: str) -> dict[str, Any] | None:
        with self.engine.connect() as connection:
            artifact = connection.execute(select(tables.artifacts).where(tables.artifacts.c.id == artifact_id)).mappings().one_or_none()
        if artifact is None or artifact["kind"] not in {"eval_case_attachment", "eval_case_workspace"} or artifact["media_type"] != "application/zip":
            return None
        return self._row_dict(artifact)
