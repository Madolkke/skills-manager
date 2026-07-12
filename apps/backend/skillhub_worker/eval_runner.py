from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from skillhub.models.store import SkillHubStore
from skillhub_worker.eval_steps import run_steps
from skillhub_worker.heartbeat import record_eval_running, record_idle
from skillhub_worker.laminar_client import LaminarClient, LaminarEvalRefs
from skillhub_worker.opencode_client import OpencodeClient
from skillhub_worker.results import (
    initial_skill_usage,
    opencode_agent_id,
    opencode_selection,
    persist_metadata,
    record_laminar_refs,
)
from skillhub_worker.workspace import materialize_case_workspace, materialize_opencode_agent


logger = logging.getLogger(__name__)


def run_eval_once(detail: dict[str, Any], store: SkillHubStore, client: OpencodeClient, laminar: LaminarClient, *, config) -> bool:
    """Execute one claimed eval case run job."""
    run = detail["eval_case_run"]
    job = detail.get("job") or {}
    eval_case_run_id = run["id"]
    job_id = str(job.get("id") or "")
    attempts = int(job.get("attempts") or 1)
    metadata: dict[str, Any] = {
        "runner": "opencode_laminar",
        "current_stage": "preparing",
        "current_stage_label": "准备工作目录",
        "step_results": [],
    }
    logger.info(
        "eval job claimed worker_id=%s eval_case_run_id=%s job_id=%s attempt=%s max_attempts=%s skill_version_id=%s",
        config.worker_id,
        eval_case_run_id,
        job_id,
        attempts,
        config.max_attempts,
        run.get("skill_version_id"),
    )
    record_eval_running(store, detail, config=config)
    try:
        opencode_model = opencode_selection(run.get("run_context"))
        agent_id = opencode_agent_id(run.get("run_context"))
        metadata["opencode_model_selection"] = opencode_model
        paths = materialize_case_workspace(detail, host_root=config.workdir_host, container_root=config.workdir_container)
        metadata["workdir"] = paths["workdir"]
        metadata["skill_installation"] = paths["skill_installation"]
        metadata["skill_usage"] = initial_skill_usage(paths["skill_installation"])
        logger.debug(
            "eval workspace ready eval_case_run_id=%s host_workdir=%s workdir=%s skill_slug=%s",
            eval_case_run_id,
            paths["host_workdir"],
            paths["workdir"],
            metadata["skill_usage"]["skill_slug"],
        )

        agent_snapshot = None
        if agent_id:
            agent = store.enabled_opencode_agent_for_run(agent_id=agent_id)
            agent_snapshot = materialize_opencode_agent(Path(paths["host_workdir"]), paths["workdir"], agent)
            metadata["opencode_agent"] = agent_snapshot
            logger.info("eval opencode agent materialized eval_case_run_id=%s agent_id=%s", eval_case_run_id, agent_id)
        persist_metadata(store, eval_case_run_id, metadata)

        case_version = detail["case_version"]
        steps = list(case_version.get("steps") or [])
        metadata["current_stage"] = "creating_laminar_datapoint"
        metadata["current_stage_label"] = "创建 Laminar 测评记录"
        persist_metadata(store, eval_case_run_id, metadata)
        logger.debug("laminar datapoint creating eval_case_run_id=%s case_version_id=%s", eval_case_run_id, case_version["id"])
        refs = laminar.create_eval_datapoint(
            name=f"SkillHub Eval {eval_case_run_id}",
            data={"case_version_id": case_version["id"], "steps": steps},
            target={"all_steps_must_pass": True},
            metadata={"eval_case_run_id": eval_case_run_id, "skill_version_id": run["skill_version_id"]},
        )
        record_laminar_refs(metadata, refs)
        if refs.error:
            logger.warning(
                "laminar datapoint unavailable; evaluation continuing eval_case_run_id=%s configured=%s",
                eval_case_run_id,
                refs.configured,
            )

        metadata["current_stage"] = "checking_opencode_health"
        metadata["current_stage_label"] = "检查 Opencode 服务"
        persist_metadata(store, eval_case_run_id, metadata)
        logger.debug("opencode health check starting eval_case_run_id=%s", eval_case_run_id)
        client.health()
        metadata["current_stage"] = "creating_opencode_session"
        metadata["current_stage_label"] = "创建 Opencode 会话"
        persist_metadata(store, eval_case_run_id, metadata)
        logger.info("opencode session creating eval_case_run_id=%s workdir=%s", eval_case_run_id, paths["workdir"])
        session_id = client.create_session(title=f"SkillHub Eval {eval_case_run_id}", directory=paths["workdir"])
        metadata["opencode_session_id"] = session_id
        metadata["session_id"] = session_id
        persist_metadata(store, eval_case_run_id, metadata)
        logger.info("opencode session created eval_case_run_id=%s opencode_session_id=%s", eval_case_run_id, session_id)

        passed, actual_output, failure_reason = run_steps(
            steps=steps,
            store=store,
            client=client,
            eval_case_run_id=eval_case_run_id,
            session_id=session_id,
            paths=paths,
            metadata=metadata,
            opencode_model=opencode_model,
            agent_id=agent_id,
        )
        _update_laminar(
            store=store,
            laminar=laminar,
            refs=refs,
            metadata=metadata,
            opencode_model=opencode_model,
            agent_snapshot=agent_snapshot,
            eval_case_run_id=eval_case_run_id,
        )
        metadata["current_stage"] = "completed"
        metadata["current_stage_label"] = "测评完成"
        store.finalize_eval_case_run(
            eval_case_run_id=eval_case_run_id,
            passed=passed,
            actual_output=actual_output,
            actor=config.worker_id,
            runner_metadata={**metadata, "reason": failure_reason},
        )
        logger.info(
            "eval job completed eval_case_run_id=%s job_id=%s passed=%s step_count=%s",
            eval_case_run_id,
            job_id,
            passed,
            len(steps),
        )
    except Exception as exc:
        failed_stage = str(metadata.get("current_stage") or "")
        metadata["current_stage"] = "failed"
        metadata["current_stage_label"] = "测评器执行失败"
        logger.exception(
            "eval job failed eval_case_run_id=%s job_id=%s attempt=%s max_attempts=%s stage=%s",
            eval_case_run_id,
            job_id,
            attempts,
            config.max_attempts,
            failed_stage,
        )
        persist_metadata(store, eval_case_run_id, metadata)
        error = str(exc) or exc.__class__.__name__
        if attempts < config.max_attempts:
            store.retry_eval_case_run_job(eval_case_run_id=eval_case_run_id, error=error)
            logger.warning("eval job retry scheduled eval_case_run_id=%s job_id=%s next_attempt=%s", eval_case_run_id, job_id, attempts + 1)
        else:
            store.fail_eval_case_run(eval_case_run_id=eval_case_run_id, error=error)
            logger.error("eval job marked failed eval_case_run_id=%s job_id=%s", eval_case_run_id, job_id)
    finally:
        record_idle(store, config=config)
    return True


def _update_laminar(
    *,
    store: SkillHubStore,
    laminar: LaminarClient,
    refs: LaminarEvalRefs,
    metadata: dict[str, Any],
    opencode_model: dict[str, str],
    agent_snapshot: dict[str, Any] | None,
    eval_case_run_id: str,
) -> None:
    metadata["current_stage"] = "updating_laminar"
    metadata["current_stage_label"] = "写入 Laminar 测评结果"
    metadata.pop("current_step", None)
    persist_metadata(store, eval_case_run_id, metadata)
    if not refs.evaluation_id or not refs.datapoint_id:
        logger.debug("laminar datapoint update skipped eval_case_run_id=%s reason=missing_reference", eval_case_run_id)
        return
    scores = _scores(metadata["step_results"])
    logger.debug("laminar datapoint updating eval_case_run_id=%s score_count=%s", eval_case_run_id, len(scores))
    laminar_error = laminar.update_datapoint(
        refs=refs,
        executor_output={
            "step_results": metadata["step_results"],
            "opencode_model_selection": opencode_model,
            "opencode_agent": agent_snapshot,
            "skill_installation": metadata["skill_installation"],
            "skill_usage": metadata["skill_usage"],
        },
        scores=scores,
        metadata=metadata,
    )
    if laminar_error:
        metadata["laminar_error"] = laminar_error
        persist_metadata(store, eval_case_run_id, metadata)
        logger.warning("laminar datapoint update failed; evaluation continuing eval_case_run_id=%s", eval_case_run_id)


def _scores(step_results: list[dict[str, Any]]) -> dict[str, int]:
    scores = {"passed": 1 if all(item["passed"] for item in step_results if item["status"] != "skipped") else 0}
    for item in step_results:
        if item["status"] != "skipped":
            scores[f"step.{item['step_id']}"] = 1 if item["passed"] else 0
            for assertion in item.get("assertions") or []:
                scores[f"step.{item['step_id']}.assertion.{assertion['assertion_id']}"] = 1 if assertion["passed"] else 0
    return scores
