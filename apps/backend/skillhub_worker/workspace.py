from __future__ import annotations

import base64
from pathlib import Path, PurePosixPath
import re
import shutil
import zipfile

from skillhub_worker.opencode_trace import compact_message_output


BUILDER_AGENT_ID = "skillhub-skill-builder"
BUILDER_AGENT_PROMPT = """你是 SkillHub 的 Skill 创建 Agent，负责帮助用户创建高质量的 Agent Skill。

工作方式：
- 先通过对话澄清 Skill 的使用场景、触发条件、输入输出、约束和可复用资源。
- 当用户要求创建、补充或修改 Skill 内容时，直接在当前工作目录创建或更新文本文件。
- 必须创建根目录 SKILL.md，并使用 YAML frontmatter，且只包含 name 和 description。
- name 必须是小写字母、数字和连字符，最多 64 个字符。
- description 必须说明 Skill 能力和触发场景。
- SKILL.md 正文只写对后续 Agent 真正有用的简洁指令。
- 仅在确有必要时创建 references/、scripts/ 或 assets/ 下的文本文件。
- 不要创建 README、安装指南、变更日志或与 Skill 运行无关的说明文件。
- 只写 UTF-8 文本文件，不写二进制文件。
- 不要运行命令，不要访问网络，不要依赖当前工作目录外的文件。
"""

BUILDER_TOOLS = {
    "bash": False,
    "edit": True,
    "glob": True,
    "grep": True,
    "list": True,
    "read": True,
    "write": True,
}


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


def _reject_builder_workspace_path(path: PurePosixPath) -> None:
    _reject_unsafe_path(path)
    raw = path.as_posix()
    if raw == ".opencode" or raw.startswith(".opencode/"):
        raise RuntimeError(f"Unsafe builder workspace path: {path}")


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


def _safe_agent_id(value: str) -> str:
    clean = value.strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", clean):
        raise RuntimeError(f"Unsafe Opencode agent id: {value}")
    return clean


def _agent_markdown(agent: dict) -> str:
    frontmatter = {
        "description": str(agent.get("description") or ""),
        "mode": "primary",
        "model": _agent_model(agent),
        "temperature": _agent_temperature(agent.get("temperature")),
        "permission": _agent_permission(agent.get("permission")),
        "steps": list(agent.get("steps") or []),
    }
    lines = ["---"]
    for key, value in frontmatter.items():
        if value in (None, "", [], {}):
            continue
        lines.extend(_yaml_line(key, value))
    lines.extend(["---", "", str(agent.get("prompt") or "").strip(), ""])
    return "\n".join(lines)


def _builder_agent_markdown() -> str:
    lines = [
        "---",
        "description: 'Create SkillHub Agent Skill bundle drafts from user requirements.'",
        "mode: primary",
        "permission:",
        "  bash: deny",
        "  edit: allow",
        "  glob: allow",
        "  grep: allow",
        "  list: allow",
        "  read: allow",
        "  write: allow",
        "---",
        "",
        BUILDER_AGENT_PROMPT.strip(),
        "",
    ]
    return "\n".join(lines)


def _agent_model(agent: dict) -> str:
    provider_id = str(agent.get("provider_id") or "").strip()
    model_id = str(agent.get("model_id") or "").strip()
    return f"{provider_id}/{model_id}" if provider_id and model_id else ""


def _agent_temperature(value) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _agent_permission(value) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    result: dict[str, str] = {}
    for key, enabled in value.items():
        if isinstance(enabled, bool):
            result[str(key)] = "allow" if enabled else "deny"
    return result


def _yaml_line(key: str, value) -> list[str]:
    if isinstance(value, bool):
        return [f"{key}: {'true' if value else 'false'}"]
    if isinstance(value, (int, float)):
        return [f"{key}: {value}"]
    if isinstance(value, str):
        return [f"{key}: {value!r}"]
    if isinstance(value, list):
        lines = [f"{key}:"]
        lines.extend(f"  - {str(item)!r}" for item in value)
        return lines
    if isinstance(value, dict):
        lines = [f"{key}:"]
        for item_key, item_value in value.items():
            if isinstance(item_value, bool):
                rendered = "true" if item_value else "false"
            else:
                rendered = repr(item_value)
            lines.append(f"  {item_key}: {rendered}")
        return lines
    return [f"{key}: {str(value)!r}"]


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
