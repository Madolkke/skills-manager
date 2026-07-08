from __future__ import annotations

import logging
from os import environ
from typing import Any, Mapping

import httpx

from skillhub.models.errors import InvariantError
from skillhub.models.store import SkillHubStore
from skillhub.services.base import ServiceBase


logger = logging.getLogger(__name__)


class OpencodeService(ServiceBase[SkillHubStore]):
    def __init__(self, store: SkillHubStore, environment: Mapping[str, str] = environ, *, timeout_seconds: float = 10) -> None:
        super().__init__(store)
        self.base_url = environment.get("OPENCODE_BASE_URL", "http://127.0.0.1:4096").rstrip("/")
        self.timeout_seconds = timeout_seconds

    def provider_options(self) -> dict[str, Any]:
        try:
            logger.debug("opencode providers loading base_url=%s", self.base_url)
            response = httpx.get(f"{self.base_url}/config/providers", timeout=self.timeout_seconds, trust_env=False)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("opencode providers load failed base_url=%s error_type=%s", self.base_url, exc.__class__.__name__)
            raise InvariantError("无法读取 Opencode provider 配置，请确认 Opencode 服务可用。") from exc
        payload = response.json()
        result = sanitize_opencode_providers(payload)
        logger.info("opencode providers loaded base_url=%s provider_count=%s", self.base_url, len(result["providers"]))
        return result

    def agent_options(self) -> dict[str, Any]:
        return {"agents": self.store.list_enabled_opencode_agents()}


def sanitize_opencode_providers(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise InvariantError("Opencode provider 配置格式不正确。")
    defaults = payload.get("default")
    default_map = {str(key): str(value) for key, value in defaults.items()} if isinstance(defaults, dict) else {}
    providers = []
    for provider in payload.get("providers") or []:
        if not isinstance(provider, dict):
            continue
        provider_id = _clean_text(provider.get("id"))
        if not provider_id:
            continue
        models = [_sanitize_model(model) for model in _model_values(provider.get("models"))]
        models = [model for model in models if model is not None]
        providers.append(
            {
                "id": provider_id,
                "name": _clean_text(provider.get("name")) or provider_id,
                "source": _clean_text(provider.get("source")) or "",
                "default_model_id": default_map.get(provider_id),
                "models": models,
            }
        )
    return {"providers": providers}


def _model_values(value: Any) -> list[Any]:
    if isinstance(value, dict):
        return list(value.values())
    if isinstance(value, list):
        return value
    return []


def _sanitize_model(model: Any) -> dict[str, Any] | None:
    if not isinstance(model, dict):
        return None
    model_id = _clean_text(model.get("id"))
    if not model_id:
        return None
    capabilities = model.get("capabilities")
    limit = model.get("limit")
    return {
        "id": model_id,
        "name": _clean_text(model.get("name")) or model_id,
        "family": _clean_text(model.get("family")) or "",
        "status": _clean_text(model.get("status")) or "",
        "capabilities": _safe_object(capabilities),
        "limit": _safe_object(limit),
    }


def _clean_text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _safe_object(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}
