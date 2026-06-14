from __future__ import annotations

from skillhub.infrastructure.db.repository_impl.skills.commands import SkillCommandMixin
from skillhub.infrastructure.db.repository_impl.skills.read_models import ReadModelMixin
from skillhub.infrastructure.db.repository_impl.skills.roles import RoleMixin


class SkillRepositoryMixin(SkillCommandMixin, ReadModelMixin, RoleMixin):
    pass
