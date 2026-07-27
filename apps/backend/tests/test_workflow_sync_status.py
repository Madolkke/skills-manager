from __future__ import annotations

import pytest

from skillhub.models.operations.workflows.helpers import WorkflowHelperMixin


@pytest.mark.parametrize(
    ("current_sync", "latest_revision", "expected"),
    [
        ({"workflow_revision": 2}, 1, "in_sync"),
        ({"workflow_revision": 1}, 2, "workflow_changed"),
        (None, 2, "skill_changed"),
        (None, 1, "diverged"),
    ],
)
def test_sync_status_uses_current_version_source_before_latest_sync(
    current_sync: dict | None,
    latest_revision: int,
    expected: str,
) -> None:
    latest = {
        "workflow_revision": latest_revision,
        "skill_version_id": "skillver-latest",
        "created_at": "2026-07-28T00:00:00Z",
    }
    result = WorkflowHelperMixin()._workflow_sync_status_from_latest(
        latest=latest,
        current_sync=current_sync,
        workflow={"revision": 2},
        skill={"current_version_id": "skillver-current"},
    )
    assert result["status"] == expected
