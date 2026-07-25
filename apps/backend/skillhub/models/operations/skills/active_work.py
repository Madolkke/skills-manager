from __future__ import annotations

from sqlalchemy import and_, or_, select

from skillhub.models.errors import ConflictError
from skillhub.models.schema import orm

ACTIVE_JOB_STATUSES = ("queued", "running")
ACTIVE_EVAL_STATUSES = ("queued", "running")
ACTIVE_PUBLISH_STATUSES = ("queued", "releasing")


def reject_active_skill_work(session, *, skill_id: str, action: str) -> None:
    active_eval = session.execute(
        select(orm.EvalCaseRun.id)
        .where(orm.EvalCaseRun.skill_id == skill_id)
        .where(orm.EvalCaseRun.status.in_(ACTIVE_EVAL_STATUSES))
        .limit(1)
    ).scalar_one_or_none()
    active_publish = session.execute(
        select(orm.PublishRecord.id)
        .where(orm.PublishRecord.skill_id == skill_id)
        .where(orm.PublishRecord.status.in_(ACTIVE_PUBLISH_STATUSES))
        .limit(1)
    ).scalar_one_or_none()
    case_job_ids = select(orm.EvalCaseRun.job_id).where(orm.EvalCaseRun.skill_id == skill_id)
    publish_record_ids = select(orm.PublishRecord.id).where(orm.PublishRecord.skill_id == skill_id)
    active_job = session.execute(
        select(orm.Job.id)
        .where(orm.Job.status.in_(ACTIVE_JOB_STATUSES))
        .where(
            or_(
                orm.Job.id.in_(case_job_ids),
                and_(
                    orm.Job.type == "publish_release",
                    orm.Job.payload["publish_record_id"].as_string().in_(publish_record_ids),
                ),
            )
        )
        .limit(1)
    ).scalar_one_or_none()
    if active_eval or active_publish or active_job:
        raise ConflictError(f"Skill 存在排队中或运行中的任务，任务结束后才能{action}。")
