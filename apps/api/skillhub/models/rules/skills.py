from __future__ import annotations

from skillhub.models.rules.semver import normalize_semver


def initial_skill_version(version: str | None) -> str:
    """Normalize the first Skill version, defaulting to 0.0.1."""
    return normalize_semver(version or "0.0.1")


def skill_change_summary(value: str | None) -> str:
    """Normalize a Skill version change summary for service-created commands."""
    return value or "Initial version."
