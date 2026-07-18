from __future__ import annotations

from typing import Any

from skillhub.models.entities import utc_now
from skillhub.models.schema import orm


class ArtifactCommandMixin:
    def create_text_artifact(self, *, kind: str, namespace: str, content: str, actor: str) -> dict[str, Any]:
        created_at = utc_now()
        with self._write_session() as connection:
            artifact_id = self._insert_text_artifact(
                connection,
                kind=kind,
                namespace=namespace,
                content=content,
                actor=actor,
                created_at=created_at,
            )
            artifact = connection.execute(orm.select_entity(orm.Artifact).where(orm.Artifact.id == artifact_id)).mappings().one()
        return self._row_dict(artifact)
