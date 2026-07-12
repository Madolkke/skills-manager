from __future__ import annotations

from typing import Any

from sqlalchemy import select, update

from skillhub.models.entities import utc_now
from skillhub.models.errors import InvariantError
from skillhub.models.schema import tables


class ReviewNotificationCommandMixin:
    def mark_notification(self, *, notification_id: str, read: bool, actor: str) -> dict[str, Any]:
        updated_at = utc_now()
        with self.engine.begin() as connection:
            row = (
                connection.execute(
                    select(tables.notifications)
                    .where(tables.notifications.c.id == notification_id)
                    .where(tables.notifications.c.recipient_actor_id == actor)
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise InvariantError("Notification not found for actor.")
            connection.execute(
                update(tables.notifications)
                .where(tables.notifications.c.id == notification_id)
                .values(read_at=updated_at if read else None)
            )
            return self._row_dict(
                connection.execute(select(tables.notifications).where(tables.notifications.c.id == notification_id)).mappings().one()
            )
