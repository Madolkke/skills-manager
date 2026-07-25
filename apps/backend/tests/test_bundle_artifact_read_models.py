import json

import pytest

from skillhub.models.operations.bundles.artifacts import BundleArtifactMixin


def bundle_artifact(manifest: dict[str, object]) -> dict[str, object]:
    return {"kind": "skill_bundle", "content_text": json.dumps(manifest)}


def test_bundle_description_reads_trimmed_manifest_metadata() -> None:
    artifact = bundle_artifact({"metadata": {"description": "  Review access controls.  "}, "files": []})

    assert BundleArtifactMixin()._bundle_description_from_artifact(artifact) == "Review access controls."


@pytest.mark.parametrize(
    "artifact",
    [
        {"kind": "skill_bundle", "content_text": "{not-json"},
        bundle_artifact({"metadata": []}),
        bundle_artifact({"metadata": {"description": "   "}}),
        {**bundle_artifact({"metadata": {"description": "Ignored."}}), "kind": "result"},
    ],
)
def test_bundle_description_is_absent_for_unreadable_metadata(artifact: dict[str, object]) -> None:
    assert BundleArtifactMixin()._bundle_description_from_artifact(artifact) is None
