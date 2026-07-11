from __future__ import annotations

from skillhub.models.operations.skills.commands import SkillCommandMixin
from skillhub.models.operations.skills.groups import GroupMixin
from skillhub.models.operations.skills.read_models import ReadModelMixin
from skillhub.models.operations.skills.roles import RoleMixin
from skillhub.models.operations.skills.tag_catalog import TagCatalogMixin
from skillhub.models.operations.skills.tag_cascades import TagCascadeMixin


class SkillStoreMixin(SkillCommandMixin, ReadModelMixin, TagCatalogMixin, TagCascadeMixin, GroupMixin, RoleMixin):
    pass
