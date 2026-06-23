from __future__ import annotations

from skillhub.infrastructure.db.repository_impl.reviews.admin import ReviewAdminMixin
from skillhub.infrastructure.db.repository_impl.reviews.commands import ReviewCommandMixin
from skillhub.infrastructure.db.repository_impl.reviews.helpers import ReviewHelperMixin
from skillhub.infrastructure.db.repository_impl.reviews.queries import ReviewQueryMixin


class ReviewCommandQueryMixin(ReviewCommandMixin, ReviewQueryMixin, ReviewAdminMixin, ReviewHelperMixin):
    pass
