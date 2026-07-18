from __future__ import annotations

from skillhub.models.store import SkillHubStore
from skillhub.services.admin_access import AdminAccessService
from skillhub.services.admin_catalog import AdminCatalogService
from skillhub.services.admin_runtime import AdminRuntimeService


class AdminService:
    """Temporary compatibility facade over focused admin use-case services."""

    def __init__(self, store: SkillHubStore):
        self.catalog = AdminCatalogService(store)
        self.access = AdminAccessService(store)
        self.runtime = AdminRuntimeService(store)

    def __getattr__(self, name: str):
        for service in (self.catalog, self.access, self.runtime):
            if hasattr(service, name):
                return getattr(service, name)
        raise AttributeError(name)
