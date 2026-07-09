from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from skillhub.models.store import SkillHubStore
from skillhub_worker.heartbeat import record_builder_running, record_idle
from skillhub_worker.opencode_client import OpencodeClient
from skillhub_worker.opencode_trace import compact_message_output, extract_opencode_trace, new_opencode_messages, opencode_message_ids
from skillhub_worker.results import compact_message_response, payload_text, public_opencode_trace
from skillhub_worker.workspace import (
    BUILDER_AGENT_ID,
    BUILDER_TOOLS,
    materialize_builder_workspace,
    render_builder_prompt,
    scan_builder_draft_files,
    sync_builder_workspace_files,
)


logger = logging.getLogger(__name__)


def run_builder_once(store: SkillHubStore, client: OpencodeClient, *, config) -> bool:
    """Execute one claimed skill builder job."""
    detail = store.claim_next_skill_builder_job(worker_id=config.worker_id)
    if detail is None:
        logger.debug("skill builder poll empty worker_id=%s", config.worker_id)
        return False
    session = detail["session"]
    message = detail["message"]
    job = detail["job"]
    session_id = session["id"]
    job_id = job["id"]
    logger.info(
        "skill builder job claimed worker_id=%s session_id=%s job_id=%s message_id=%s intent=%s",
        config.worker_id,
        session_id,
        job_id,
        message.get("id"),
        message.get("intent") or "chat",
    )
    record_builder_running(store, detail, config=config)
    try:
        _record_progress(store, session_id=session_id, job_id=job_id, stage="preparing_workspace")
        paths = materialize_builder_workspace(session=session, host_root=config.workdir_host, container_root=config.workdir_container)
        workspace_files = list(session.get("workspace_files") or session.get("draft_files") or [])
        sync_builder_workspace_files(Path(paths["host_workdir"]), workspace_files)
        logger.debug(
            "skill builder workspace ready session_id=%s job_id=%s host_workdir=%s file_count=%s",
            session_id,
            job_id,
            paths["host_workdir"],
            len(workspace_files),
        )
        _record_progress(store, session_id=session_id, job_id=job_id, stage="checking_opencode")
        client.health()
        if session.get("opencode_session_id"):
            opencode_session_id = str(session["opencode_session_id"])
        else:
            _record_progress(store, session_id=session_id, job_id=job_id, stage="creating_opencode_session")
            opencode_session_id = _create_session(client, session_id, paths)
        _record_progress(store, session_id=session_id, job_id=job_id, stage="loading_message_history")
        messages_before = client.list_messages(session_id=opencode_session_id, directory=paths["workdir"])
        seen_message_ids = opencode_message_ids(messages_before)
        prompt = render_builder_prompt(user_content=str(message.get("content") or ""), intent=str(message.get("intent") or "chat"))
        logger.debug(
            "skill builder message sending session_id=%s job_id=%s opencode_session_id=%s provider_id=%s model_id=%s",
            session_id,
            job_id,
            opencode_session_id,
            payload_text(job.get("payload"), "provider_id"),
            payload_text(job.get("payload"), "model_id"),
        )
        _record_progress(store, session_id=session_id, job_id=job_id, stage="sending_message")
        response = client.send_message(
            session_id=opencode_session_id,
            prompt=prompt,
            directory=paths["workdir"],
            provider_id=payload_text(job.get("payload"), "provider_id") or None,
            model_id=payload_text(job.get("payload"), "model_id") or None,
            agent_id=BUILDER_AGENT_ID,
            tools=BUILDER_TOOLS,
        )
        _record_progress(store, session_id=session_id, job_id=job_id, stage="scanning_workspace")
        message_history = client.list_messages(session_id=opencode_session_id, directory=paths["workdir"])
        new_messages = new_opencode_messages(message_history, seen_message_ids, seen_count=len(messages_before))
        trace_source: object = new_messages or response
        assistant_output = compact_message_output(trace_source)
        draft_files = scan_builder_draft_files(Path(paths["host_workdir"]))
        _record_progress(store, session_id=session_id, job_id=job_id, stage="saving_result")
        store.complete_skill_builder_job(
            session_id=session_id,
            job_id=job_id,
            assistant_content=assistant_output,
            intent=str(message.get("intent") or "chat"),
            draft_files=draft_files,
            opencode_session_id=opencode_session_id,
            workdir=paths["workdir"],
            metadata={
                "runner": "opencode_skill_builder",
                "builder_agent": BUILDER_AGENT_ID,
                "builder_agent_file": paths["builder_agent_file"],
                "message_response": compact_message_response(response),
                "opencode_trace": public_opencode_trace(extract_opencode_trace(trace_source)),
                "draft_file_count": len(draft_files),
                "workspace_file_count": len(draft_files),
            },
        )
        logger.info(
            "skill builder job completed session_id=%s job_id=%s opencode_session_id=%s draft_file_count=%s",
            session_id,
            job_id,
            opencode_session_id,
            len(draft_files),
        )
    except Exception as exc:
        logger.exception("skill builder job failed session_id=%s job_id=%s", session_id, job_id)
        store.fail_skill_builder_job(session_id=session_id, job_id=job_id, error=str(exc) or exc.__class__.__name__)
    finally:
        record_idle(store, config=config)
    return True


def _create_session(client: OpencodeClient, session_id: str, paths: dict[str, Any]) -> str:
    logger.info("skill builder opencode session creating session_id=%s workdir=%s", session_id, paths["workdir"])
    opencode_session_id = client.create_session(title=f"SkillHub Builder {session_id}", directory=paths["workdir"])
    logger.info("skill builder opencode session created session_id=%s opencode_session_id=%s", session_id, opencode_session_id)
    return opencode_session_id


def _record_progress(store: SkillHubStore, *, session_id: str, job_id: str, stage: str) -> None:
    try:
        store.update_skill_builder_job_progress(session_id=session_id, job_id=job_id, stage=stage)
    except Exception:
        logger.warning("skill builder progress update failed session_id=%s job_id=%s stage=%s", session_id, job_id, stage, exc_info=True)
