from __future__ import annotations

from skillhub.models.operations.skills.commands import SkillCommandMixin
from skillhub.models.operations.skills.read_models import ReadModelMixin
from skillhub.models.operations.skills.roles import RoleMixin


class SkillStoreMixin(SkillCommandMixin, ReadModelMixin, RoleMixin):
    pass
