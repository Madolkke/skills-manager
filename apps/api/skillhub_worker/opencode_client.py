from __future__ import annotations

from typing import Any

import httpx


class OpencodeClient:
    def __init__(self, *, base_url: str, timeout_seconds: float) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = httpx.Timeout(timeout_seconds)

    def health(self) -> None:
        response = httpx.get(f"{self.base_url}/global/health", timeout=self.timeout)
        response.raise_for_status()

    def create_session(self, *, title: str, directory: str) -> str:
        response = httpx.post(
            f"{self.base_url}/session",
            params={"directory": directory},
            json={"title": title},
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        session_id = payload.get("id")
        if not isinstance(session_id, str) or not session_id:
            raise RuntimeError("Opencode session response did not include an id.")
        return session_id

    def send_message(self, *, session_id: str, prompt: str, provider_id: str | None, model_id: str | None, directory: str) -> dict[str, Any]:
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
        response = httpx.post(
            f"{self.base_url}/session/{session_id}/message",
            params={"directory": directory},
            json=body,
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()
