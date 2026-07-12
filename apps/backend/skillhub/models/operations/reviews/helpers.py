"""评审 Store 内部辅助能力的兼容组合入口。"""

from skillhub.models.operations.reviews.publishing import ReviewPublishingMixin
from skillhub.models.operations.reviews.read_models import ReviewReadMixin
from skillhub.models.operations.reviews.reviewers import ReviewerSnapshotMixin


class ReviewHelperMixin(ReviewReadMixin, ReviewerSnapshotMixin, ReviewPublishingMixin):
    pass
