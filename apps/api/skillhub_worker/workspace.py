from __future__ import annotations

import base64
import json
from pathlib import Path, PurePosixPath
import shutil
import zipfile


def materialize_case_workspace(case_detail: dict, *, host_root: Path, container_root: str) -> dict[str, str]:
    run = case_detail["eval_case_run"]
    host_dir = host_root / run["id"]
    if host_dir.exists():
        shutil.rmtree(host_dir)
    skill_dir = host_dir / "skill"
    workdir = host_dir / "workdir"
    skill_dir.mkdir(parents=True)
    workdir.mkdir(parents=True)

    _write_skill_bundle(case_detail["skill_version"], skill_dir)
    workspace_artifact = case_detail["case_version"].get("workspace_artifact")
    if workspace_artifact and workspace_artifact.get("content_text"):
        _extract_zip_to_workdir(workspace_artifact["content_text"], workdir)

    container_dir = _container_path(container_root, run["id"])
    return {
        "host_dir": str(host_dir),
        "host_workdir": str(workdir),
        "container_dir": container_dir,
        "skill_dir": f"{container_dir}/skill",
        "skill_file": f"{container_dir}/skill/SKILL.md",
        "workdir": f"{container_dir}/workdir",
    }


def render_step_prompt(*, step: dict, paths: dict[str, str], step_number: int, total_steps: int) -> str:
    return (
        "你正在执行 SkillHub 的 Opencode 测试场景。\n"
        f"Skill 文件位于：{paths['skill_file']}\n"
        f"工作目录位于：{paths['workdir']}\n"
        f"当前是第 {step_number}/{total_steps} 步。\n\n"
        "请阅读 Skill 指令，并基于下面的用户输入完成本步骤任务。"
        "本轮只需要完成任务并停止，不要判断自己是否通过，也不要写 result.json。\n\n"
        f"用户输入：\n{step.get('input', '')}"
    )


def workspace_snapshot(workdir: Path) -> set[str]:
    if not workdir.exists():
        return set()
    return {
        path.relative_to(workdir).as_posix()
        for path in workdir.rglob("*")
        if path.is_file()
    }


def compact_message_output(response: object) -> str:
    text = _find_text(response)
    if text.strip():
        return text.strip()
    try:
        return json.dumps(response, ensure_ascii=False, sort_keys=True)
    except TypeError:
        return str(response)


def _find_text(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(part for item in value if (part := _find_text(item)).strip())
    if not isinstance(value, dict):
        return ""
    for key in ("text", "content", "message", "output"):
        part = _find_text(value.get(key))
        if part.strip():
            return part
    if "parts" in value:
        return _find_text(value["parts"])
    return ""


def _write_skill_bundle(skill_version: dict, skill_dir: Path) -> None:
    files = skill_version.get("bundle_files") or []
    if not files:
        content_ref = skill_version.get("content_ref") or {}
        raise RuntimeError(f"SkillVersion has no readable skill bundle artifact: {content_ref.get('locator', skill_version.get('id'))}")
    for file in files:
        relative = PurePosixPath(str(file["path"]))
        _reject_unsafe_path(relative)
        target = skill_dir / Path(*relative.parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(str(file.get("content_text") or ""), encoding="utf-8")


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
