from __future__ import annotations

from typing import Any

import httpx

from skillhub_worker import opencode_client


class FakeHttpClient:
    init_args: dict[str, Any] | None = None

    def __init__(self, **kwargs: Any) -> None:
        self.requests: list[dict[str, Any]] = []
        FakeHttpClient.init_args = kwargs

    def get(self, url: str) -> httpx.Response:
        self.requests.append({"method": "GET", "url": url})
        return httpx.Response(200, json={"healthy": True}, request=httpx.Request("GET", f"http://opencode.test{url}"))

    def post(self, url: str, **kwargs: Any) -> httpx.Response:
        self.requests.append({"method": "POST", "url": url, **kwargs})
        request = httpx.Request("POST", f"http://opencode.test{url}")
        if url == "/session":
            return httpx.Response(200, json={"id": "session_1"}, request=request)
        return httpx.Response(200, json={"id": "message_1", "parts": [{"type": "text", "text": "ok"}]}, request=request)


def test_opencode_client_ignores_environment_proxy(monkeypatch):
    monkeypatch.setattr(opencode_client.httpx, "Client", FakeHttpClient)

    client = opencode_client.OpencodeClient(base_url="http://127.0.0.1:4096", timeout_seconds=30)

    assert FakeHttpClient.init_args is not None
    assert FakeHttpClient.init_args["trust_env"] is False
    assert FakeHttpClient.init_args["base_url"] == "http://127.0.0.1:4096"
    assert isinstance(FakeHttpClient.init_args["timeout"], httpx.Timeout)
    client.health()


def test_send_message_omits_model_when_not_configured(monkeypatch):
    monkeypatch.setattr(opencode_client.httpx, "Client", FakeHttpClient)
    client = opencode_client.OpencodeClient(base_url="http://127.0.0.1:4096", timeout_seconds=30)

    client.send_message(session_id="session_1", prompt="hello", provider_id=None, model_id=None, directory="/workspace/run")

    request = client._client.requests[-1]
    assert request["json"]["parts"] == [{"type": "text", "text": "hello"}]
    assert "model" not in request["json"]


def test_send_message_includes_model_when_configured(monkeypatch):
    monkeypatch.setattr(opencode_client.httpx, "Client", FakeHttpClient)
    client = opencode_client.OpencodeClient(base_url="http://127.0.0.1:4096", timeout_seconds=30)

    client.send_message(
        session_id="session_1",
        prompt="hello",
        provider_id="deepseek",
        model_id="deepseek-v4-flash",
        directory="/workspace/run",
    )

    request = client._client.requests[-1]
    assert request["json"]["model"] == {"providerID": "deepseek", "modelID": "deepseek-v4-flash"}
