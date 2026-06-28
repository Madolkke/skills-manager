from __future__ import annotations

import base64
import io
import json
from pathlib import Path
import zipfile

import pytest

from skillhub_worker.opencode_trace import extract_opencode_trace, new_opencode_messages, opencode_message_ids
from skillhub_worker.workspace import compact_message_output, materialize_case_workspace, render_step_prompt, _extract_zip_to_workdir


def zip_payload(files: dict[str, str]) -> str:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for path, content in files.items():
            archive.writestr(path, content)
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def test_extract_zip_rejects_path_traversal(tmp_path: Path):
    with pytest.raises(RuntimeError, match="Unsafe zip path"):
        _extract_zip_to_workdir(zip_payload({"../escape.txt": "bad"}), tmp_path)


@pytest.mark.parametrize("path", ["safe/..\\escape.txt", "C:/escape.txt", "C:\\escape.txt"])
def test_extract_zip_rejects_windows_style_unsafe_paths(tmp_path: Path, path: str):
    with pytest.raises(RuntimeError, match="Unsafe zip path"):
        _extract_zip_to_workdir(zip_payload({path: "bad"}), tmp_path)


def test_extract_zip_copies_files_to_workdir(tmp_path: Path):
    _extract_zip_to_workdir(zip_payload({"docs/input.txt": "hello"}), tmp_path)

    assert (tmp_path / "docs" / "input.txt").read_text(encoding="utf-8") == "hello"


def test_materialize_case_workspace_installs_skill_as_opencode_project_skill(tmp_path: Path):
    paths = materialize_case_workspace(_case_detail(), host_root=tmp_path, container_root="/workspace/eval-runs")

    host_workdir = Path(paths["host_workdir"])
    skill_dir = host_workdir / ".opencode" / "skills" / "test-skill"
    assert (skill_dir / "SKILL.md").read_text(encoding="utf-8").startswith("---\nname: test-skill")
    assert (skill_dir / "guides" / "example.md").read_text(encoding="utf-8") == "Use the fixture."
    assert (host_workdir / "docs" / "input.txt").read_text(encoding="utf-8") == "hello"
    assert paths["workdir"] == "/workspace/eval-runs/evalcase_1/workdir"
    assert paths["opencode_skill_dir"] == "/workspace/eval-runs/evalcase_1/workdir/.opencode/skills/test-skill"
    assert paths["skill_installation"]["skill_slug"] == "test-skill"
    assert paths["skill_installation"]["mode"] == "project_isolated"


def test_materialize_case_workspace_strips_legacy_single_bundle_root(tmp_path: Path):
    detail = _case_detail()
    detail["skill_version"]["bundle_files"] = [
        {"path": "test-skill/SKILL.md", "content_text": "---\nname: test-skill\ndescription: Test.\n---\nBody"},
        {"path": "test-skill/guides/example.md", "content_text": "Use the fixture."},
    ]

    paths = materialize_case_workspace(detail, host_root=tmp_path, container_root="/workspace/eval-runs")

    skill_dir = Path(paths["host_workdir"]) / ".opencode" / "skills" / "test-skill"
    assert (skill_dir / "SKILL.md").is_file()
    assert (skill_dir / "guides" / "example.md").is_file()


def test_compact_message_output_prefers_text_parts():
    payload = {"parts": [{"type": "text", "text": "hello"}]}

    assert compact_message_output(payload) == "hello"


def test_compact_message_output_omits_opencode_reasoning_parts():
    payload = [
        {
            "info": {"role": "user"},
            "parts": [{"type": "text", "text": "输出 helloworld"}],
        },
        {
            "info": {"role": "assistant"},
            "parts": [
                {"type": "reasoning", "text": "I should output helloworld."},
                {"type": "text", "text": "helloworld"},
            ],
        },
    ]

    assert compact_message_output(payload) == "helloworld"


def test_extract_opencode_trace_captures_reasoning_text_and_tool_calls():
    payload = [
        {"info": {"role": "user"}, "parts": [{"type": "text", "text": "请读取 README.md"}]},
        {
            "info": {"role": "assistant", "finish": "stop", "providerID": "deepseek", "modelID": "deepseek-v4-flash"},
            "parts": [
                {"type": "reasoning", "text": "I should inspect README.md."},
                {
                    "type": "tool",
                    "tool": "skill",
                    "callID": "call_skill",
                    "state": {
                        "status": "completed",
                        "input": {"name": "test-skill"},
                        "output": "Loaded test-skill",
                        "title": "Loaded skill: test-skill",
                        "metadata": {
                            "name": "test-skill",
                            "dir": "/workspace/run/.opencode/skills/test-skill",
                            "truncated": False,
                        },
                    },
                },
                {
                    "type": "tool",
                    "tool": "read",
                    "callID": "call_1",
                    "state": {
                        "status": "completed",
                        "input": {"filePath": "README.md"},
                        "output": "README content",
                    },
                },
                {"type": "text", "text": "已读取 README.md"},
            ],
        },
    ]

    trace = extract_opencode_trace(payload)

    assert trace["text_output"] == "已读取 README.md"
    assert trace["reasoning_text"] == "I should inspect README.md."
    assert trace["finish"] == "stop"
    assert trace["provider_id"] == "deepseek"
    assert trace["model_id"] == "deepseek-v4-flash"
    assert trace["tool_calls"] == [
        {
            "tool": "skill",
            "status": "completed",
            "input": {"name": "test-skill"},
            "output_preview": "Loaded test-skill",
            "call_id": "call_skill",
            "title": "Loaded skill: test-skill",
            "metadata": {
                "name": "test-skill",
                "dir": "/workspace/run/.opencode/skills/test-skill",
                "truncated": False,
            },
        },
        {
            "tool": "read",
            "status": "completed",
            "input": {"filePath": "README.md"},
            "output_preview": "README content",
            "call_id": "call_1",
            "title": "",
            "metadata": {},
        }
    ]


def test_new_opencode_messages_uses_message_ids_and_count_fallback():
    before = [{"id": "msg_1"}, {"id": "msg_2"}]
    after = [{"id": "msg_1"}, {"id": "msg_2"}, {"id": "msg_3"}]
    no_ids_before = [{"info": {"role": "assistant"}}]
    no_ids_after = [{"info": {"role": "assistant"}}, {"info": {"role": "assistant"}, "parts": [{"type": "text", "text": "new"}]}]

    assert new_opencode_messages(after, opencode_message_ids(before), seen_count=len(before)) == [{"id": "msg_3"}]
    assert new_opencode_messages(no_ids_after, opencode_message_ids(no_ids_before), seen_count=len(no_ids_before)) == [
        {"info": {"role": "assistant"}, "parts": [{"type": "text", "text": "new"}]}
    ]


def test_compact_message_output_falls_back_to_json():
    payload = {"id": "msg_1", "finish": "stop"}

    assert compact_message_output(payload) == json.dumps(payload, ensure_ascii=False, sort_keys=True)


def test_step_prompt_is_exact_user_input_without_skillhub_injection():
    prompt = render_step_prompt(
        step={"input": "请生成 README.md"},
        paths={"skill_file": "/workspace/run/.opencode/skills/test-skill/SKILL.md", "workdir": "/workspace/run"},
        step_number=1,
        total_steps=2,
    )

    assert prompt == "请生成 README.md"
    assert "SkillHub" not in prompt
    assert "SKILL.md" not in prompt


def _case_detail() -> dict:
    return {
        "eval_case_run": {"id": "evalcase_1", "skill_id": "skill_1", "skill_version_id": "skillver_1"},
        "skill": {"id": "skill_1", "slug": "test-skill"},
        "skill_version": {
            "id": "skillver_1",
            "skill_id": "skill_1",
            "version": "0.0.1",
            "content_digest": "digest-1",
            "bundle_files": [
                {"path": "SKILL.md", "content_text": "---\nname: test-skill\ndescription: Test.\n---\nBody"},
                {"path": "guides/example.md", "content_text": "Use the fixture."},
            ],
        },
        "case_version": {
            "workspace_artifact": {"content_text": zip_payload({"docs/input.txt": "hello"})},
        },
    }
