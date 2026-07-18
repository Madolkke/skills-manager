from __future__ import annotations

import base64
import re
import shutil
import zipfile
from pathlib import Path, PurePosixPath


def write_skill_bundle(skill_version: dict, skill_dir: Path, *, skill_slug: str) -> None:
    files = skill_version.get("bundle_files") or []
    if not files:
        content_ref = skill_version.get("content_ref") or {}
        raise RuntimeError(f"SkillVersion has no readable skill bundle artifact: {content_ref.get('locator', skill_version.get('id'))}")
    for relative, file in normalized_bundle_files(files):
        target = skill_dir / Path(*relative.parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(file_content(file))
    if not (skill_dir / "SKILL.md").is_file():
        raise RuntimeError(f"SkillVersion bundle does not install a root SKILL.md for skill {skill_slug}.")


def extract_zip_to_workdir(content_base64: str, workdir: Path) -> None:
    archive = workdir / ".workspace.zip"
    archive.write_bytes(base64.b64decode(content_base64, validate=True))
    with zipfile.ZipFile(archive) as zip_file:
        for member in zip_file.infolist():
            relative = PurePosixPath(member.filename)
            reject_unsafe_path(relative)
            if member.is_dir():
                (workdir / Path(*relative.parts)).mkdir(parents=True, exist_ok=True)
                continue
            target = workdir / Path(*relative.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with zip_file.open(member) as source, target.open("wb") as destination:
                shutil.copyfileobj(source, destination)
    archive.unlink(missing_ok=True)


def reject_unsafe_path(path: PurePosixPath) -> None:
    raw = path.as_posix()
    if "\\" in raw or "\x00" in raw:
        raise RuntimeError(f"Unsafe zip path: {path}")
    if path.is_absolute() or any(part in {"", ".", ".."} or _is_windows_drive(part) for part in path.parts):
        raise RuntimeError(f"Unsafe zip path: {path}")


def reject_builder_workspace_path(path: PurePosixPath) -> None:
    reject_unsafe_path(path)
    raw = path.as_posix()
    if raw == ".opencode" or raw.startswith(".opencode/"):
        raise RuntimeError(f"Unsafe builder workspace path: {path}")


def skill_slug(case_detail: dict) -> str:
    value = str(case_detail.get("skill", {}).get("slug") or "").strip()
    if not value:
        value = bundle_skill_name(case_detail["skill_version"])
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", value):
        raise RuntimeError(f"Unsafe skill slug: {value}")
    return value


def bundle_skill_name(skill_version: dict) -> str:
    for relative, file in normalized_bundle_files(skill_version.get("bundle_files") or []):
        if relative.as_posix() != "SKILL.md":
            continue
        lines = file_content(file).decode("utf-8").splitlines()
        for line in lines[1:]:
            if line.strip() == "---":
                break
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            if key.strip() == "name":
                return value.strip().strip("\"'")
    raise RuntimeError(f"SkillVersion has no readable skill name: {skill_version.get('id')}")


def normalized_bundle_files(files: list[dict]) -> list[tuple[PurePosixPath, dict]]:
    normalized = []
    for file in files:
        relative = PurePosixPath(str(file["path"]))
        reject_unsafe_path(relative)
        normalized.append((relative, file))
    if any(path.as_posix() == "SKILL.md" for path, _file in normalized):
        return normalized
    roots = {path.parts[0] for path, _file in normalized if len(path.parts) > 1}
    has_root_files = any(len(path.parts) == 1 for path, _file in normalized)
    if len(roots) == 1 and not has_root_files:
        stripped = [(PurePosixPath(*path.parts[1:]), file) for path, file in normalized]
        if any(path.as_posix() == "SKILL.md" for path, _file in stripped):
            return stripped
    return normalized


def file_content(file: dict) -> bytes:
    if isinstance(file.get("content_base64"), str):
        return base64.b64decode(file["content_base64"], validate=True)
    return str(file.get("content_text") or "").encode("utf-8")


def _is_windows_drive(part: str) -> bool:
    return len(part) == 2 and part[1] == ":"
