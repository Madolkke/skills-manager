from __future__ import annotations

import base64
import json
import re
from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
from pathlib import PurePosixPath
from typing import Any

import yaml

from skillhub.models.errors import FieldError, FieldInvariantError, InvariantError


@dataclass(frozen=True, slots=True)
class RenamedSkillBundle:
    manifest_text: str
    digest: str
    file_count: int


def normalize_skill_display_name(value: str | None) -> str | None:
    if value is None:
        return None
    clean = value.strip()
    if not clean:
        return None
    if len(clean) > 120:
        raise FieldInvariantError(
            "Skill display name is too long.",
            [
                FieldError(
                    field="display_name",
                    message="中文名不能超过 120 个字符。",
                    code="skill.display_name_too_long",
                )
            ],
        )
    return clean


def rename_skill_bundle(manifest_text: str, *, new_slug: str) -> RenamedSkillBundle:
    """Return a validated Bundle snapshot whose root Skill name uses the new slug."""
    manifest = _manifest(manifest_text)
    metadata = manifest.get("metadata")
    files = manifest.get("files")
    if not isinstance(metadata, dict) or not isinstance(files, list) or not files:
        raise InvariantError("Skill Bundle manifest must contain metadata and files.")

    renamed_files: list[dict[str, Any]] = []
    seen_paths: set[str] = set()
    found_skill_markdown = False
    for raw_file in files:
        file, content = _validated_file(raw_file)
        path = file["path"]
        if path in seen_paths:
            raise InvariantError("Skill Bundle manifest contains duplicate file paths.")
        seen_paths.add(path)
        if path == "SKILL.md":
            if file.get("content_text") is None:
                raise InvariantError("Skill Bundle SKILL.md must be UTF-8 text.")
            content = _rename_frontmatter(file["content_text"], new_slug).encode("utf-8")
            file.pop("content_base64", None)
            file["content_text"] = content.decode("utf-8")
            found_skill_markdown = True
        file["size_bytes"] = len(content)
        file["sha256"] = sha256(content).hexdigest()
        renamed_files.append(file)

    if not found_skill_markdown:
        raise InvariantError("Skill Bundle must contain SKILL.md at its root.")

    renamed = deepcopy(manifest)
    renamed["metadata"] = {**metadata, "name": new_slug}
    renamed["files"] = sorted(renamed_files, key=lambda item: item["path"])
    result = json.dumps(renamed, ensure_ascii=False, sort_keys=True, indent=2)
    return RenamedSkillBundle(
        manifest_text=result,
        digest=sha256(result.encode("utf-8")).hexdigest(),
        file_count=len(renamed_files),
    )


def _manifest(value: str) -> dict[str, Any]:
    if not value.strip():
        raise InvariantError("Skill Bundle artifact content is empty.")
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise InvariantError("Skill Bundle artifact manifest is invalid JSON.") from exc
    if not isinstance(parsed, dict):
        raise InvariantError("Skill Bundle artifact manifest must be an object.")
    return parsed


def _validated_file(value: Any) -> tuple[dict[str, Any], bytes]:
    if not isinstance(value, dict):
        raise InvariantError("Skill Bundle manifest contains an invalid file.")
    path = value.get("path")
    if not isinstance(path, str) or not _safe_path(path):
        raise InvariantError("Skill Bundle manifest contains an unsafe file path.")
    has_text = isinstance(value.get("content_text"), str)
    has_base64 = isinstance(value.get("content_base64"), str)
    if has_text == has_base64:
        raise InvariantError("Skill Bundle file must contain exactly one content representation.")
    try:
        content = (
            value["content_text"].encode("utf-8")
            if has_text
            else base64.b64decode(value["content_base64"], validate=True)
        )
    except (ValueError, UnicodeError) as exc:
        raise InvariantError("Skill Bundle file content is invalid.") from exc
    if value.get("size_bytes") != len(content) or value.get("sha256") != sha256(content).hexdigest():
        raise InvariantError("Skill Bundle file size or digest does not match its content.")
    return deepcopy(value), content


def _safe_path(value: str) -> bool:
    if "\\" in value or "\x00" in value:
        return False
    path = PurePosixPath(value)
    return bool(value) and not path.is_absolute() and all(part not in {"", ".", ".."} for part in path.parts)


def _rename_frontmatter(value: str, new_slug: str) -> str:
    lines = value.splitlines()
    if not lines or lines[0].strip() != "---":
        raise InvariantError("SKILL.md must start with YAML frontmatter.")
    end = next((index for index, line in enumerate(lines[1:], start=1) if line.strip() == "---"), None)
    if end is None:
        raise InvariantError("SKILL.md frontmatter must end with ---.")
    try:
        metadata = yaml.safe_load("\n".join(lines[1:end]))
    except yaml.YAMLError as exc:
        raise InvariantError("SKILL.md frontmatter is invalid YAML.") from exc
    if not isinstance(metadata, dict):
        raise InvariantError("SKILL.md frontmatter must be an object.")
    name_lines = [index for index, line in enumerate(lines[1:end], start=1) if re.match(r"^name\s*:", line)]
    if len(name_lines) != 1:
        raise InvariantError("SKILL.md frontmatter must contain one simple top-level name field.")

    renamed_lines = list(lines)
    renamed_lines[name_lines[0]] = f"name: {new_slug}"
    try:
        renamed_metadata = yaml.safe_load("\n".join(renamed_lines[1:end]))
    except yaml.YAMLError as exc:
        raise InvariantError("SKILL.md name cannot be safely replaced.") from exc
    expected_metadata = deepcopy(metadata)
    expected_metadata["name"] = new_slug
    if renamed_metadata != expected_metadata:
        raise InvariantError("SKILL.md name cannot be safely replaced without changing other frontmatter fields.")

    result = "\n".join(renamed_lines)
    return f"{result}\n" if value.endswith("\n") else result
