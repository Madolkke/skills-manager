from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any
from uuid import UUID

from lmnr import LaminarClient as LmnrSdkClient


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LaminarEvalRefs:
    configured: bool
    evaluation_id: str | None = None
    datapoint_id: str | None = None
    error: str | None = None


class LaminarClient:
    def __init__(self, *, base_url: str, project_api_key: str | None, http_port: int | None, timeout_seconds: float) -> None:
        self.base_url = base_url.rstrip("/") or None
        self.project_api_key = (project_api_key or "").strip() or None
        self.http_port = http_port
        self.timeout_seconds = int(timeout_seconds)
        self._sdk: LmnrSdkClient | None = None

    @property
    def configured(self) -> bool:
        return bool(self.project_api_key)

    def create_eval_datapoint(self, *, name: str, data: dict[str, Any], target: dict[str, Any], metadata: dict[str, Any]) -> LaminarEvalRefs:
        if not self.configured:
            logger.warning("laminar datapoint skipped reason=missing_project_api_key")
            return LaminarEvalRefs(configured=False, error="Laminar 未配置 LMNR_PROJECT_API_KEY。")
        try:
            logger.debug("laminar datapoint creating name=%s base_url=%s", name, self.base_url or "default")
            client = self._client()
            evaluation_id = client.evals.create_evaluation(name=name, metadata=metadata)
            datapoint_id = client.evals.create_datapoint(
                eval_id=evaluation_id,
                data=data,
                target=target,
                metadata=metadata,
            )
            refs = LaminarEvalRefs(
                configured=True,
                evaluation_id=str(evaluation_id),
                datapoint_id=str(datapoint_id),
            )
            logger.info("laminar datapoint created evaluation_id=%s datapoint_id=%s", evaluation_id, datapoint_id)
            return refs
        except Exception as exc:
            logger.exception("laminar datapoint create failed")
            return LaminarEvalRefs(configured=True, error=self._format_error("初始化 Laminar 测评记录失败", exc))

    def update_datapoint(self, *, refs: LaminarEvalRefs, executor_output: dict[str, Any], scores: dict[str, Any], metadata: dict[str, Any]) -> str | None:
        if not self.configured or not refs.evaluation_id or not refs.datapoint_id:
            logger.warning("laminar datapoint update skipped configured=%s evaluation_id_present=%s datapoint_id_present=%s", self.configured, bool(refs.evaluation_id), bool(refs.datapoint_id))
            return refs.error
        try:
            logger.debug("laminar datapoint updating evaluation_id=%s datapoint_id=%s score_count=%s", refs.evaluation_id, refs.datapoint_id, len(scores))
            self._client().evals.update_datapoint(
                eval_id=UUID(refs.evaluation_id),
                datapoint_id=UUID(refs.datapoint_id),
                executor_output={
                    **executor_output,
                    "metadata": {key: value for key, value in metadata.items() if key != "step_results"},
                },
                scores=scores,
            )
            logger.info("laminar datapoint updated evaluation_id=%s datapoint_id=%s", refs.evaluation_id, refs.datapoint_id)
            return None
        except Exception as exc:
            logger.exception("laminar datapoint update failed evaluation_id=%s datapoint_id=%s", refs.evaluation_id, refs.datapoint_id)
            return self._format_error("写入 Laminar 测评结果失败", exc)

    def query(self, sql: str, parameters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        if not self.configured:
            return []
        return self._client().sql.query(sql, parameters=parameters or {})

    def _client(self) -> LmnrSdkClient:
        if self._sdk is None:
            self._sdk = LmnrSdkClient(
                base_url=self.base_url,
                project_api_key=self.project_api_key,
                port=self.http_port,
                timeout=self.timeout_seconds,
            )
        return self._sdk

    def _format_error(self, message: str, exc: Exception) -> str:
        reason = str(exc).strip() or exc.__class__.__name__
        endpoint = self.base_url or "默认 Laminar API"
        if self.http_port:
            endpoint = f"{endpoint}:{self.http_port}"
        return f"{message}: {reason}（{endpoint}）"
