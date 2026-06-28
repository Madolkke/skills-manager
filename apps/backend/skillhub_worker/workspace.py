from __future__ import annotations

import base64
from pathlib import Path, PurePosixPath
import re
import shutil
import zipfile

from skillhub_worker.opencode_trace import compact_message_output


def materialize_case_workspace(case_detail: dict, *, host_root: Path, container_root: str) -> dict[str, str]:
    run = case_detail["eval_case_run"]
    skill_version = case_detail["skill_version"]
    host_dir = host_root / run["id"]
    if host_dir.exists():
        shutil.rmtree(host_dir)
    workdir = host_dir / "workdir"
    workdir.mkdir(parents=True)

    workspace_artifact = case_detail["case_version"].get("workspace_artifact")
    if workspace_artifact and workspace_artifact.get("content_text"):
        _extract_zip_to_workdir(workspace_artifact["content_text"], workdir)

    skill_slug = _skill_slug(case_detail)
    skill_dir = workdir / ".opencode" / "skills" / skill_slug
    skill_dir.mkdir(parents=True, exist_ok=True)
    _write_skill_bundle(skill_version, skill_dir, skill_slug=skill_slug)

    container_dir = _container_path(container_root, run["id"])
    container_workdir = f"{container_dir}/workdir"
    container_skill_dir = f"{container_workdir}/.opencode/skills/{skill_slug}"
    return {
        "host_dir": str(host_dir),
        "host_workdir": str(workdir),
        "container_dir": container_dir,
        "skill_dir": container_skill_dir,
        "skill_file": f"{container_skill_dir}/SKILL.md",
        "opencode_skill_dir": container_skill_dir,
        "workdir": container_workdir,
        "skill_installation": {
            "skill_id": case_detail.get("skill", {}).get("id") or skill_version.get("skill_id") or run.get("skill_id") or "",
            "skill_version_id": skill_version.get("id") or run.get("skill_version_id") or "",
            "skill_slug": skill_slug,
            "version": skill_version.get("version") or "",
            "bundle_digest": skill_version.get("content_digest") or (skill_version.get("content_ref") or {}).get("digest") or "",
            "host_skill_dir": str(skill_dir),
            "opencode_skill_dir": container_skill_dir,
            "mode": "project_isolated",
        },
    }


def render_step_prompt(*, step: dict, paths: dict[str, str], step_number: int, total_steps: int) -> str:
    _ = (paths, step_number, total_steps)
    return str(step.get("input") or "")


def workspace_snapshot(workdir: Path) -> set[str]:
    if not workdir.exists():
        return set()
    return {
        path.relative_to(workdir).as_posix()
        for path in workdir.rglob("*")
        if path.is_file()
    }


def _write_skill_bundle(skill_version: dict, skill_dir: Path, *, skill_slug: str) -> None:
    files = skill_version.get("bundle_files") or []
    if not files:
        content_ref = skill_version.get("content_ref") or {}
        raise RuntimeError(f"SkillVersion has no readable skill bundle artifact: {content_ref.get('locator', skill_version.get('id'))}")
    for relative, file in _normalized_bundle_files(files):
        target = skill_dir / Path(*relative.parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(_file_content(file))
    if not (skill_dir / "SKILL.md").is_file():
        raise RuntimeError(f"SkillVersion bundle does not install a root SKILL.md for skill {skill_slug}.")


def _extract_zip_to_workdir(content_base64: str, workdir: Path) -> None:
    archive = workdir / ".workspace.zip"
    archive.write_bytes(base64.b64decode(content_base64, validate=True))
    with zipfile.ZipFile(archive) as zip_file:
        for member in zip_file.infolist():
            relative = PurePosixPath(member.filename)
            _reject_unsafe_path(relative)
            if member.is_dir():
                (workdir / Path(*relative.parts)).mkdir(parents=True, exist_ok=True)
                continue
            target = workdir / Path(*relative.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with zip_file.open(member) as source, target.open("wb") as destination:
                shutil.copyfileobj(source, destination)
    archive.unlink(missing_ok=True)


def _reject_unsafe_path(path: PurePosixPath) -> None:
    raw = path.as_posix()
    if "\\" in raw or "\x00" in raw:
        raise RuntimeError(f"Unsafe zip path: {path}")
    if path.is_absolute() or any(part in {"", ".", ".."} or _is_windows_drive(part) for part in path.parts):
        raise RuntimeError(f"Unsafe zip path: {path}")


def _container_path(container_root: str, run_id: str) -> str:
    return f"{container_root.rstrip('/')}/{run_id}"


def _is_windows_drive(part: str) -> bool:
    return len(part) == 2 and part[1] == ":"


def _skill_slug(case_detail: dict) -> str:
    skill_slug = str(case_detail.get("skill", {}).get("slug") or "").strip()
    if not skill_slug:
        skill_slug = _bundle_skill_name(case_detail["skill_version"])
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", skill_slug):
        raise RuntimeError(f"Unsafe skill slug: {skill_slug}")
    return skill_slug


def _bundle_skill_name(skill_version: dict) -> str:
    for relative, file in _normalized_bundle_files(skill_version.get("bundle_files") or []):
        if relative.as_posix() != "SKILL.md":
            continue
        text = _file_content(file).decode("utf-8")
        lines = text.splitlines()
        for line in lines[1:]:
            if line.strip() == "---":
                break
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            if key.strip() == "name":
                return value.strip().strip("\"'")
    raise RuntimeError(f"SkillVersion has no readable skill name: {skill_version.get('id')}")


def _normalized_bundle_files(files: list[dict]) -> list[tuple[PurePosixPath, dict]]:
    normalized = []
    for file in files:
        relative = PurePosixPath(str(file["path"]))
        _reject_unsafe_path(relative)
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


def _file_content(file: dict) -> bytes:
    if isinstance(file.get("content_base64"), str):
        return base64.b64decode(file["content_base64"], validate=True)
    return str(file.get("content_text") or "").encode("utf-8")
