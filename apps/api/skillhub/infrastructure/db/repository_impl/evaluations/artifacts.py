from __future__ import annotations

from typing import Any

from sqlalchemy import select

from skillhub.domain.models import utc_now
from skillhub.infrastructure.db import tables


class ArtifactCommandMixin:
    def create_text_artifact(self, *, kind: str, namespace: str, content: str, actor: str) -> dict[str, Any]:
        created_at = utc_now()
        with self.engine.begin() as connection:
            artifact_id = self._insert_text_artifact(
                connection,
                kind=kind,
                namespace=namespace,
                content=content,
                actor=actor,
                created_at=created_at,
            )
            artifact = connection.execute(select(tables.artifacts).where(tables.artifacts.c.id == artifact_id)).mappings().one()
        return self._row_dict(artifact)
