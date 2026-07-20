from __future__ import annotations

import logging
import time

from skillhub.bootstrap.logging_config import configure_logging
from skillhub.models.schema.database import create_postgres_engine, resolve_database_url
from skillhub.models.schema.migrations import verify_database_revision
from skillhub.models.store import SkillHubStore
from skillhub_worker.builder_runner import run_builder_once
from skillhub_worker.config import load_config
from skillhub_worker.eval_runner import run_eval_once
from skillhub_worker.heartbeat import record_idle
from skillhub_worker.laminar_client import LaminarClient
from skillhub_worker.opencode_client import OpencodeClient
from skillhub_worker.publish_runner import run_publish_once

logger = logging.getLogger(__name__)


def run_once(store: SkillHubStore, client: OpencodeClient, laminar: LaminarClient, *, config) -> bool:
    """Claim and execute one eval or skill builder job."""
    _recover_stale_jobs(store, config=config)
    record_idle(store, config=config)
    if run_publish_once(store, config=config):
        return True
    detail = store.claim_next_eval_case_run_job(worker_id=config.worker_id)
    if detail is not None:
        return run_eval_once(detail, store, client, laminar, config=config)
    logger.debug("eval poll empty worker_id=%s", config.worker_id)
    return run_builder_once(store, client, config=config)


def main() -> None:
    """Run the worker polling loop."""
    configure_logging()
    config = load_config()
    logger.info(
        "starting skillhub worker worker_id=%s workdir_host=%s workdir_container=%s opencode_base_url=%s laminar_base_url=%s laminar_configured=%s poll_seconds=%s timeout_seconds=%s max_attempts=%s stale_after_seconds=%s publish_timeout_seconds=%s",
        config.worker_id,
        config.workdir_host,
        config.workdir_container,
        config.opencode_base_url,
        config.laminar_base_url,
        bool(config.laminar_project_api_key),
        config.poll_interval_seconds,
        config.timeout_seconds,
        config.max_attempts,
        config.stale_after_seconds,
        config.publish_release_timeout_seconds,
    )
    config.workdir_host.mkdir(parents=True, exist_ok=True)
    engine = create_postgres_engine(resolve_database_url())
    verify_database_revision(engine)
    store = SkillHubStore(engine)
    client = OpencodeClient(base_url=config.opencode_base_url, timeout_seconds=config.timeout_seconds)
    laminar = LaminarClient(
        base_url=config.laminar_base_url,
        http_port=config.laminar_http_port,
        project_api_key=config.laminar_project_api_key,
        timeout_seconds=config.timeout_seconds,
    )
    while True:
        try:
            did_work = run_once(store, client, laminar, config=config)
        except Exception:
            logger.exception("worker loop failed worker_id=%s; retrying", config.worker_id)
            time.sleep(min(max(config.poll_interval_seconds, 0.1), 5.0))
            continue
        if not did_work:
            logger.debug("worker sleeping worker_id=%s seconds=%s", config.worker_id, config.poll_interval_seconds)
            time.sleep(config.poll_interval_seconds)


def _recover_stale_jobs(store: SkillHubStore, *, config) -> None:
    recover = getattr(store, "recover_stale_jobs", None)
    if recover is None:
        return
    try:
        recovered = recover(
            stale_after_seconds=config.stale_after_seconds,
            max_eval_attempts=config.max_attempts,
        )
        if any(recovered.values()):
            logger.warning("stale jobs recovered worker_id=%s recovered=%s", config.worker_id, recovered)
    except Exception:
        logger.exception("stale job recovery failed worker_id=%s", config.worker_id)


if __name__ == "__main__":
    main()
