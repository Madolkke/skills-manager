from __future__ import annotations

import logging
from typing import Any

import httpx


logger = logging.getLogger(__name__)


class OpencodeClient:
    def __init__(self, *, base_url: str, timeout_seconds: float) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = httpx.Timeout(timeout_seconds)
        self._client = httpx.Client(base_url=self.base_url, timeout=self.timeout, trust_env=False)

    def health(self) -> None:
        logger.debug("opencode health check starting base_url=%s", self.base_url)
        response = self._client.get("/global/health")
        response.raise_for_status()
        logger.debug("opencode health check completed base_url=%s status=%s", self.base_url, response.status_code)

    def create_session(self, *, title: str, directory: str) -> str:
        logger.debug("opencode create session starting base_url=%s directory=%s", self.base_url, directory)
        response = self._client.post(
            "/session",
            params={"directory": directory},
            json={"title": title},
        )
        response.raise_for_status()
        payload = response.json()
        session_id = payload.get("id")
        if not isinstance(session_id, str) or not session_id:
            raise RuntimeError("Opencode session response did not include an id.")
        logger.info("opencode create session completed session_id=%s status=%s", session_id, response.status_code)
        return session_id

    def send_message(
        self,
        *,
        session_id: str,
        prompt: str,
        directory: str,
        provider_id: str | None = None,
        model_id: str | None = None,
        agent_id: str | None = None,
        tools: dict[str, bool] | None = None,
    ) -> dict[str, Any]:
        logger.debug(
            "opencode send message starting session_id=%s directory=%s provider_id=%s model_id=%s agent_id=%s",
            session_id,
            directory,
            provider_id or "",
            model_id or "",
            agent_id or "",
        )
        body: dict[str, Any] = {
            "parts": [{"type": "text", "text": prompt}],
            "tools": tools or {
                "bash": True,
                "edit": True,
                "glob": True,
                "grep": True,
                "list": True,
                "read": True,
                "write": True,
            },
        }
        if agent_id:
            body["agent"] = agent_id
        if provider_id and model_id:
            body["model"] = {"providerID": provider_id, "modelID": model_id}
        response = self._client.post(
            f"/session/{session_id}/message",
            params={"directory": directory},
            json=body,
        )
        response.raise_for_status()
        payload = response.json()
        logger.debug("opencode send message completed session_id=%s status=%s", session_id, response.status_code)
        return payload

    def list_messages(self, *, session_id: str, directory: str) -> list[dict[str, Any]]:
        logger.debug("opencode list messages starting session_id=%s directory=%s", session_id, directory)
        response = self._client.get(
            f"/session/{session_id}/message",
            params={"directory": directory},
        )
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, list):
            messages = [item for item in payload if isinstance(item, dict)]
            logger.debug("opencode list messages completed session_id=%s count=%s", session_id, len(messages))
            return messages
        if isinstance(payload, dict) and isinstance(payload.get("data"), list):
            messages = [item for item in payload["data"] if isinstance(item, dict)]
            logger.debug("opencode list messages completed session_id=%s count=%s", session_id, len(messages))
            return messages
        logger.debug("opencode list messages completed session_id=%s count=0", session_id)
        return []
