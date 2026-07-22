from __future__ import annotations

from skillhub.models.operations.skills.deletion import SkillDeletionMixin
from skillhub.models.operations.skills.external_upsert import ExternalSkillUpsertCommandMixin
from skillhub.models.operations.skills.initial import SkillCreateCommandMixin
from skillhub.models.operations.skills.updates import SkillUpdateCommandMixin
from skillhub.models.operations.skills.versions import SkillVersionCommandMixin


class SkillCommandMixin(
    SkillCreateCommandMixin,
    SkillVersionCommandMixin,
    SkillUpdateCommandMixin,
    SkillDeletionMixin,
    ExternalSkillUpsertCommandMixin,
):
    pass
