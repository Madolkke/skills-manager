"""HTTP schema 兼容导出。

请求模型按资源域存放在 ``request_models``，保留本模块以稳定现有 View 和测试的 import 路径。
"""

from skillhub.views.request_models.admin import *  # noqa: F403
from skillhub.views.request_models.common import *  # noqa: F403
from skillhub.views.request_models.evaluations import *  # noqa: F403
from skillhub.views.request_models.misc import *  # noqa: F403
from skillhub.views.request_models.reviews import *  # noqa: F403
from skillhub.views.request_models.skill_builder import *  # noqa: F403
from skillhub.views.request_models.skills import *  # noqa: F403
from skillhub.views.request_models.workflows import *  # noqa: F403
