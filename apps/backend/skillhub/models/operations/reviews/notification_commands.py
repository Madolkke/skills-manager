from __future__ import annotations

from typing import Any

from sqlalchemy import update

from skillhub.models.entities import utc_now
from skillhub.models.errors import InvariantError
from skillhub.models.schema import orm


class ReviewNotificationCommandMixin:
    def mark_notification(self, *, notification_id: str, read: bool, actor: str) -> dict[str, Any]:
        updated_at = utc_now()
        with self._write_session() as connection:
            row = (
                connection.execute(
                    orm.select_entity(orm.Notification)
                    .where(orm.Notification.id == notification_id)
                    .where(orm.Notification.recipient_actor_id == actor)
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise InvariantError("Notification not found for actor.")
            connection.execute(
                update(orm.Notification)
                .where(orm.Notification.id == notification_id)
                .values(read_at=updated_at if read else None)
            )
            return self._row_dict(
                connection.execute(orm.select_entity(orm.Notification).where(orm.Notification.id == notification_id)).mappings().one()
            )
