from __future__ import annotations

import logging

from skillhub.models.store import SkillHubStore
from skillhub.services.publish_release import perform_publish_release, publish_artifact_from_read_model
from skillhub_worker.heartbeat import record_idle, record_publish_running, renew_execution_lease

logger = logging.getLogger(__name__)


def run_publish_once(store: SkillHubStore, *, config) -> bool:
    claim = getattr(store, "claim_next_publish_release_job", None)
    if claim is None:
        return False
    detail = claim(worker_id=config.worker_id)
    if detail is None:
        return False
    job = detail["job"]
    record = detail["record"]
    execution = detail["execution"]
    logger.info(
        "publish job claimed job_id=%s publish_record_id=%s worker_id=%s attempt=%s",
        job["id"],
        record["id"],
        execution["worker_id"],
        execution["attempt"],
    )
    record_publish_running(store, detail, config=config)
    try:
        renew_execution_lease(store, execution)
        artifact = publish_artifact_from_read_model(
            store.publish_release_artifact(skill_version_id=detail["release_payload"]["skill_version_id"])
        )
        release_result = perform_publish_release(
            detail["release_payload"],
            artifact,
            timeout_seconds=getattr(config, "publish_release_timeout_seconds", 120),
        )
        renew_execution_lease(store, execution)
        store.complete_publish_release_job(
            publish_record_id=record["id"],
            release_result=release_result,
            **execution,
        )
        logger.info("publish release completed job_id=%s publish_record_id=%s", job["id"], record["id"])
    except Exception as exc:
        logger.exception("publish release failed job_id=%s publish_record_id=%s", job["id"], record["id"])
        store.fail_publish_release_job(
            publish_record_id=record["id"],
            error=str(exc) or exc.__class__.__name__,
            **execution,
        )
    finally:
        record_idle(store, config=config)
    return True
