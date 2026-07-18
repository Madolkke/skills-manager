from __future__ import annotations

from skillhub.models.operations.reviews.admin import ReviewAdminMixin
from skillhub.models.operations.reviews.commands import ReviewCommandMixin
from skillhub.models.operations.reviews.helpers import ReviewHelperMixin
from skillhub.models.operations.reviews.notification_commands import ReviewNotificationCommandMixin
from skillhub.models.operations.reviews.publish_commands import ReviewPublishCommandMixin
from skillhub.models.operations.reviews.publish_jobs import PublishReleaseJobMixin
from skillhub.models.operations.reviews.queries import ReviewQueryMixin


class ReviewCommandQueryMixin(
    ReviewCommandMixin,
    ReviewPublishCommandMixin,
    ReviewNotificationCommandMixin,
    ReviewQueryMixin,
    ReviewAdminMixin,
    PublishReleaseJobMixin,
    ReviewHelperMixin,
):
    pass
