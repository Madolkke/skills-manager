from __future__ import annotations

import re
from dataclasses import dataclass

from skillhub.models.errors import FieldError, FieldInvariantError

SEMVER_PATTERN = r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
_SEMVER_RE = re.compile(SEMVER_PATTERN)


@dataclass(frozen=True, order=True)
class SemVer:
    major: int
    minor: int
    patch: int
    prerelease: str = ""
    build: str = ""


def normalize_semver(value: str | None, *, field: str = "version") -> str:
    clean = (value or "").strip()
    match = _SEMVER_RE.fullmatch(clean)
    if not match:
        raise FieldInvariantError(
            "SkillVersion version must use SemVer.",
            [
                FieldError(
                    field=field,
                    message="版本号必须使用 SemVer，例如 1.0.0、1.2.3-beta.1 或 1.2.3+build.5。",
                    code="skill_version.version_invalid",
                )
            ],
        )
    return clean


def parse_semver(value: str) -> SemVer:
    match = _SEMVER_RE.fullmatch(value)
    if not match:
        raise ValueError(f"Invalid SemVer: {value}")
    return SemVer(
        major=int(match.group(1)),
        minor=int(match.group(2)),
        patch=int(match.group(3)),
        prerelease=match.group(4) or "",
        build=match.group(5) or "",
    )


def next_patch_version(current: str | None) -> str:
    if not current:
        return "0.0.1"
    parsed = parse_semver(current)
    return f"{parsed.major}.{parsed.minor}.{parsed.patch + 1}"
