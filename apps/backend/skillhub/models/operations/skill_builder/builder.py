from __future__ import annotations

from .helpers import SkillBuilderHelperMixin
from .jobs import SkillBuilderJobMixin
from .sessions import SkillBuilderSessionMixin


class SkillBuilderStoreMixin(SkillBuilderSessionMixin, SkillBuilderJobMixin, SkillBuilderHelperMixin):
    pass
