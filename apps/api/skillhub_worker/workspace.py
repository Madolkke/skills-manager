from __future__ import annotations

import base64
import json
from pathlib import Path, PurePosixPath
import shutil
import zipfile

from skillhub.application.eval_prompt_templates import prompt_template_body


def materialize_case_workspace(case_detail: dict, *, host_root: Path, container_root: str) -> dict[str, str]:
    run = case_detail["eval_case_run"]
    case_version = case_detail["case_version"]
    host_dir = host_root / run["id"]
    if host_dir.exists():
        shutil.rmtree(host_dir)
    skill_dir = host_dir / "skill"
    case_dir = host_dir / "case"
    workdir = host_dir / "workdir"
    skill_dir.mkdir(parents=True)
    case_dir.mkdir(parents=True)
    workdir.mkdir(parents=True)

    _write_skill_bundle(case_detail["skill_version"], skill_dir)
    input_text = case_version["input_artifact"].get("content_text") or ""
    expected_output = case_version["expected_output_artifact"].get("content_text") or ""
    (case_dir / "input.txt").write_text(input_text, encoding="utf-8")
    (case_dir / "expected_output.txt").write_text(expected_output, encoding="utf-8")

    attachment = case_version.get("attachment_artifact")
    if attachment and attachment.get("content_text"):
        _extract_zip_to_workdir(attachment["content_text"], workdir)

    result_path = workdir / "result.json"
    container_dir = _container_path(container_root, run["id"])
    return {
        "host_dir": str(host_dir),
        "container_dir": container_dir,
        "skill_dir": f"{container_dir}/skill",
        "skill_file": f"{container_dir}/skill/SKILL.md",
        "workdir": f"{container_dir}/workdir",
        "result_json_path": f"{container_dir}/workdir/result.json",
        "host_result_json_path": str(result_path),
        "input": input_text,
        "expected_output": expected_output,
    }


def render_prompt(case_detail: dict, paths: dict[str, str]) -> str:
    case_version = case_detail["case_version"]
    template_id = case_version.get("prompt_template_id") or "standard_pass_fail"
    custom_prompt = (case_version.get("prompt_text") or "").strip()
    body = custom_prompt if custom_prompt else prompt_template_body(template_id)
    variables = {
        "skill_dir": paths["skill_dir"],
        "skill_file": paths["skill_file"],
        "workdir": paths["workdir"],
        "input": paths["input"],
        "expected_output": paths["expected_output"],
        "result_json_path": paths["result_json_path"],
    }
    prompt = body.format(**variables)
    return (
        f"{prompt}\n\n"
        "result.json 必须是单行合法 JSON，且只能包含以下字段：\n"
        '{"passed": boolean, "actual_output": string, "reason": string}\n'
        "必须用 JSON 序列化方式写文件；字符串里的换行必须写成 \\n，不能写入未转义的真实换行，不能使用 Markdown 代码块。\n"
        "passed 表示 actual_output 是否覆盖 expected output 要求的关键点；"
        "不要因为被审查代码本身存在问题而把 passed 写为 false。"
        "actual_output 写入你实际产出的结果。"
    )


def read_runner_result(path: str) -> dict[str, str | bool]:
    result_path = Path(path)
    if not result_path.exists():
        raise RuntimeError("Opencode did not write result.json.")
    try:
        payload = json.loads(result_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError("Opencode result.json is not valid JSON.") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("passed"), bool):
        raise RuntimeError("Opencode result.json must include boolean passed.")
    if not isinstance(payload.get("actual_output"), str):
        raise RuntimeError("Opencode result.json must include string actual_output.")
    if "reason" in payload and not isinstance(payload["reason"], str):
        raise RuntimeError("Opencode result.json reason must be a string.")
    return {
        "passed": payload["passed"],
        "actual_output": payload["actual_output"],
        "reason": payload.get("reason", ""),
    }


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
    archive = workdir / ".attachment.zip"
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
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise RuntimeError(f"Unsafe zip path: {path}")


def _container_path(container_root: str, run_id: str) -> str:
    return f"{container_root.rstrip('/')}/{run_id}"
