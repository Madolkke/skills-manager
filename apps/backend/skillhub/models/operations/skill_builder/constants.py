from __future__ import annotations

from collections.abc import Mapping
from os import environ


BUILDER_JOB_TYPE = "skill_builder_message"
BUILDER_RUNNER = "opencode_skill_builder"
DEFAULT_BUILDER_STALE_AFTER_SECONDS = 600
BUILDER_PROGRESS_STAGES = {
    "queued",
    "claimed",
    "preparing_workspace",
    "checking_opencode",
    "creating_opencode_session",
    "loading_message_history",
    "sending_message",
    "scanning_workspace",
    "saving_result",
}


def builder_stale_after_seconds(environment: Mapping[str, str] = environ) -> int:
    raw = environment.get("SKILL_BUILDER_STALE_AFTER_SECONDS", "").strip()
    if not raw:
        return DEFAULT_BUILDER_STALE_AFTER_SECONDS
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_BUILDER_STALE_AFTER_SECONDS
    return value if value > 0 else DEFAULT_BUILDER_STALE_AFTER_SECONDS


def clean_builder_progress_stage(stage: str) -> str:
    value = stage.strip()
    return value if value in BUILDER_PROGRESS_STAGES else "claimed"
