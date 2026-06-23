from __future__ import annotations

from fastapi import Depends, FastAPI

from skillhub.api.auth import ActorContext, actor_dependency
from skillhub.api.database import repository_dependency
from skillhub.api.responses import result_payload
from skillhub.api.schemas import CreatePublishRecordPayload, CreateReviewRequestPayload, NotificationUpdatePayload, SubmitReviewResponsePayload
from skillhub.infrastructure.db.repositories import SqlSkillRepository


def register_review_routes(app: FastAPI) -> None:
    @app.get("/api/skills/{skill_id}/reviews")
    def skill_reviews(
        skill_id: str,
        actor: ActorContext = Depends(actor_dependency),
        repository: SqlSkillRepository = Depends(repository_dependency),
    ):
        return result_payload(repository.list_skill_reviews(skill_id=skill_id, actor=actor.id))

    @app.post("/api/skills/{skill_id}/reviews")
    def create_review(
        skill_id: str,
        payload: CreateReviewRequestPayload,
        actor: ActorContext = Depends(actor_dependency),
        repository: SqlSkillRepository = Depends(repository_dependency),
    ):
        return result_payload(
            repository.create_review_request(
                skill_id=skill_id,
                skill_version_id=payload.skill_version_id,
                publish_targets=[item.model_dump() for item in payload.publish_targets],
                actor=actor.id,
            )
        )

    @app.post("/api/reviews/{review_id}/responses")
    def submit_review_response(
        review_id: str,
        payload: SubmitReviewResponsePayload,
        actor: ActorContext = Depends(actor_dependency),
        repository: SqlSkillRepository = Depends(repository_dependency),
    ):
        return result_payload(repository.submit_review_response(review_id=review_id, score=payload.score, comment=payload.comment, actor=actor.id))

    @app.post("/api/reviews/{review_id}/close")
    def close_review(
        review_id: str,
        actor: ActorContext = Depends(actor_dependency),
        repository: SqlSkillRepository = Depends(repository_dependency),
    ):
        return result_payload(repository.close_review(review_id=review_id, actor=actor.id))

    @app.get("/api/me/reviews")
    def my_reviews(
        actor: ActorContext = Depends(actor_dependency),
        repository: SqlSkillRepository = Depends(repository_dependency),
    ):
        return result_payload(repository.list_my_reviews(actor=actor.id))

    @app.get("/api/me/notifications")
    def my_notifications(
        actor: ActorContext = Depends(actor_dependency),
        repository: SqlSkillRepository = Depends(repository_dependency),
    ):
        return result_payload(repository.list_my_notifications(actor=actor.id))

    @app.patch("/api/notifications/{notification_id}")
    def update_notification(
        notification_id: str,
        payload: NotificationUpdatePayload,
        actor: ActorContext = Depends(actor_dependency),
        repository: SqlSkillRepository = Depends(repository_dependency),
    ):
        return result_payload(repository.mark_notification(notification_id=notification_id, read=payload.read, actor=actor.id))

    @app.get("/api/skills/{skill_id}/publish")
    def skill_publish(
        skill_id: str,
        actor: ActorContext = Depends(actor_dependency),
        repository: SqlSkillRepository = Depends(repository_dependency),
    ):
        return result_payload(repository.skill_publish_overview(skill_id=skill_id, actor=actor.id))

    @app.post("/api/skills/{skill_id}/publish-records")
    def create_publish_record(
        skill_id: str,
        payload: CreatePublishRecordPayload,
        actor: ActorContext = Depends(actor_dependency),
        repository: SqlSkillRepository = Depends(repository_dependency),
    ):
        return result_payload(
            repository.create_publish_record(
                skill_id=skill_id,
                skill_version_id=payload.skill_version_id,
                review_request_id=payload.review_request_id,
                publish_target_id=payload.publish_target_id,
                actor=actor.id,
            )
        )
