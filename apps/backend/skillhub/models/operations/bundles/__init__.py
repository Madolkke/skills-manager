from __future__ import annotations

from skillhub.models.operations.bundles.artifacts import BundleArtifactMixin
from skillhub.models.operations.bundles.diff import BundleDiffMixin


class BundleStoreMixin(BundleArtifactMixin, BundleDiffMixin):
    pass
