from __future__ import annotations

from typing import Any

from skillhub.models.errors import InvariantError


class DiffQueryMixin:
    def bundle_diff(self, *, left_skill_version_id: str, right_skill_version_id: str) -> dict[str, Any]:
        with self.engine.connect() as connection:
            left_version = self._skill_version_row(connection, left_skill_version_id)
            right_version = self._skill_version_row(connection, right_skill_version_id)
            if left_version["skill_id"] != right_version["skill_id"]:
                raise InvariantError("Bundle diff requires skill versions from the same skill.")
            return self._bundle_diff_from_versions(connection, left_version, right_version)
