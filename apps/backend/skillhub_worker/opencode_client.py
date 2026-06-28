from __future__ import annotations

from typing import Any

import httpx


class OpencodeClient:
    def __init__(self, *, base_url: str, timeout_seconds: float) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = httpx.Timeout(timeout_seconds)
        self._client = httpx.Client(base_url=self.base_url, timeout=self.timeout, trust_env=False)

    def health(self) -> None:
        response = self._client.get("/global/health")
        response.raise_for_status()

    def create_session(self, *, title: str, directory: str) -> str:
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
        return session_id

    def send_message(self, *, session_id: str, prompt: str, directory: str, provider_id: str | None = None, model_id: str | None = None) -> dict[str, Any]:
        body: dict[str, Any] = {
            "parts": [{"type": "text", "text": prompt}],
            "tools": {
                "bash": True,
                "edit": True,
                "glob": True,
                "grep": True,
                "list": True,
                "read": True,
                "write": True,
            },
        }
        if provider_id and model_id:
            body["model"] = {"providerID": provider_id, "modelID": model_id}
        response = self._client.post(
            f"/session/{session_id}/message",
            params={"directory": directory},
            json=body,
        )
        response.raise_for_status()
        return response.json()

    def list_messages(self, *, session_id: str, directory: str) -> list[dict[str, Any]]:
        response = self._client.get(
            f"/session/{session_id}/message",
            params={"directory": directory},
        )
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict) and isinstance(payload.get("data"), list):
            return [item for item in payload["data"] if isinstance(item, dict)]
        return []
