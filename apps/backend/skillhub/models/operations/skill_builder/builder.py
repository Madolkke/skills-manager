from __future__ import annotations

from .helpers import SkillBuilderHelperMixin
from .jobs import SkillBuilderJobMixin
from .recovery import SkillBuilderRecoveryMixin
from .sessions import SkillBuilderSessionMixin


class SkillBuilderStoreMixin(SkillBuilderSessionMixin, SkillBuilderJobMixin, SkillBuilderRecoveryMixin, SkillBuilderHelperMixin):
    pass
