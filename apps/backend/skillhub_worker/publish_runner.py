from __future__ import annotations

import logging

from skillhub.models.store import SkillHubStore
from skillhub.services.publish_release import perform_publish_release
from skillhub_worker.heartbeat import record_idle, record_publish_running

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
    record_publish_running(store, detail, config=config)
    try:
        release_result = perform_publish_release(detail["release_payload"])
        store.complete_publish_release_job(
            job_id=job["id"],
            publish_record_id=record["id"],
            actor=config.worker_id,
            release_result=release_result,
        )
        logger.info("publish release completed job_id=%s publish_record_id=%s", job["id"], record["id"])
    except Exception as exc:
        logger.exception("publish release failed job_id=%s publish_record_id=%s", job["id"], record["id"])
        store.fail_publish_release_job(
            job_id=job["id"],
            publish_record_id=record["id"],
            actor=config.worker_id,
            error=str(exc) or exc.__class__.__name__,
        )
    finally:
        record_idle(store, config=config)
    return True
