from __future__ import annotations

from skillhub.models.operations.reviews.admin import ReviewAdminMixin
from skillhub.models.operations.reviews.commands import ReviewCommandMixin
from skillhub.models.operations.reviews.helpers import ReviewHelperMixin
from skillhub.models.operations.reviews.queries import ReviewQueryMixin


class ReviewCommandQueryMixin(ReviewCommandMixin, ReviewQueryMixin, ReviewAdminMixin, ReviewHelperMixin):
    pass
