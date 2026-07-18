from __future__ import annotations

import shutil
from pathlib import Path, PurePosixPath

from skillhub_worker.agent_workspace import (
    BUILDER_AGENT_ID,
)
from skillhub_worker.agent_workspace import (
    agent_markdown as _agent_markdown,
)
from skillhub_worker.agent_workspace import (
    builder_agent_markdown as _builder_agent_markdown,
)
from skillhub_worker.agent_workspace import (
    safe_agent_id as _safe_agent_id,
)
from skillhub_worker.opencode_trace import compact_message_output as compact_message_output
from skillhub_worker.workspace_files import (
    extract_zip_to_workdir as _extract_zip_to_workdir,
)
from skillhub_worker.workspace_files import (
    reject_builder_workspace_path as _reject_builder_workspace_path,
)
from skillhub_worker.workspace_files import (
    reject_unsafe_path as _reject_unsafe_path,
)
from skillhub_worker.workspace_files import (
    skill_slug as _skill_slug,
)
from skillhub_worker.workspace_files import (
    write_skill_bundle as _write_skill_bundle,
)


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


def materialize_opencode_agent(workdir: Path, container_workdir: str, agent: dict) -> dict[str, object]:
    agent_id = _safe_agent_id(str(agent.get("id") or ""))
    agent_dir = workdir / ".opencode" / "agents"
    agent_dir.mkdir(parents=True, exist_ok=True)
    agent_file = agent_dir / f"{agent_id}.md"
    agent_file.write_text(_agent_markdown(agent), encoding="utf-8")
    return {
        "agent_id": agent_id,
        "name": str(agent.get("name") or agent_id),
        "provider_id": str(agent.get("provider_id") or ""),
        "model_id": str(agent.get("model_id") or ""),
        "permission": dict(agent.get("permission") or {}),
        "host_agent_file": str(agent_file),
        "opencode_agent_file": f"{container_workdir}/.opencode/agents/{agent_id}.md",
        "mode": "project_isolated",
    }


def materialize_builder_workspace(*, host_root: Path, container_root: str, session: dict) -> dict[str, str]:
    session_id = str(session["id"])
    host_dir = host_root / session_id
    workdir = host_dir / "workdir"
    workdir.mkdir(parents=True, exist_ok=True)
    container_dir = _container_path(container_root, session_id)
    container_workdir = f"{container_dir}/workdir"
    agent_dir = workdir / ".opencode" / "agents"
    agent_dir.mkdir(parents=True, exist_ok=True)
    agent_file = agent_dir / f"{BUILDER_AGENT_ID}.md"
    agent_file.write_text(_builder_agent_markdown(), encoding="utf-8")
    return {
        "host_dir": str(host_dir),
        "host_workdir": str(workdir),
        "workdir": container_workdir,
        "builder_agent_file": f"{container_workdir}/.opencode/agents/{BUILDER_AGENT_ID}.md",
    }


def sync_builder_workspace_files(workdir: Path, files: list[dict]) -> None:
    workdir.mkdir(parents=True, exist_ok=True)
    desired: set[str] = set()
    for item in files:
        relative = PurePosixPath(str(item.get("path") or "").strip())
        _reject_builder_workspace_path(relative)
        desired.add(relative.as_posix())

    for path in sorted(_builder_workspace_files(workdir), key=lambda candidate: len(candidate.parts), reverse=True):
        relative = path.relative_to(workdir).as_posix()
        if relative not in desired:
            path.unlink()

    for path in sorted(_builder_workspace_dirs(workdir), key=lambda candidate: len(candidate.parts), reverse=True):
        relative = path.relative_to(workdir).as_posix()
        try:
            path.rmdir()
        except OSError:
            pass

    for item in files:
        relative = PurePosixPath(str(item.get("path") or "").strip())
        _reject_builder_workspace_path(relative)
        content = item.get("content_text")
        if not isinstance(content, str):
            raise RuntimeError(f"Builder workspace file must be UTF-8 text: {relative}")
        target = workdir / Path(*relative.parts)
        if target.exists() and target.is_dir():
            shutil.rmtree(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")


def scan_builder_draft_files(workdir: Path) -> list[dict[str, str]]:
    files: list[dict[str, str]] = []
    if not workdir.exists():
        return files
    for path in sorted(_builder_workspace_files(workdir)):
        relative = path.relative_to(workdir).as_posix()
        candidate = PurePosixPath(relative)
        _reject_unsafe_path(candidate)
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if "\x00" in content:
            continue
        files.append({"path": relative, "content_text": content})
    return files


def _builder_workspace_files(workdir: Path) -> list[Path]:
    return [path for path in _walk_builder_workspace(workdir) if path.is_file()]


def _builder_workspace_dirs(workdir: Path) -> list[Path]:
    return [path for path in _walk_builder_workspace(workdir) if path.is_dir()]


def _walk_builder_workspace(workdir: Path) -> list[Path]:
    if not workdir.exists():
        return []
    result: list[Path] = []
    stack = [workdir]
    while stack:
        current = stack.pop()
        try:
            children = list(current.iterdir())
        except OSError:
            continue
        for child in children:
            if child.name == ".opencode":
                continue
            result.append(child)
            if child.is_dir():
                stack.append(child)
    return result


def render_builder_prompt(*, user_content: str, intent: str) -> str:
    content = user_content.strip()
    if intent != "generate_draft":
        return content
    return (
        f"{content}\n\n"
        "现在请根据以上需求生成或更新 Skill 工作区文件。"
        "请直接在当前工作目录写入完整文件，不要只在回复中展示代码块。"
        "必须包含根目录 SKILL.md，并确保所有文件都是 UTF-8 文本。"
        "完成后用简短中文总结你创建或更新了哪些文件。"
    )


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


def _container_path(container_root: str, run_id: str) -> str:
    return f"{container_root.rstrip('/')}/{run_id}"
