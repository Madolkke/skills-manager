from __future__ import annotations

import base64
import io
import json
from pathlib import Path
import zipfile

import pytest

from skillhub_worker.opencode_trace import extract_opencode_trace
from skillhub_worker.workspace import compact_message_output, render_step_prompt, _extract_zip_to_workdir


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
            "tool": "read",
            "status": "completed",
            "input": {"filePath": "README.md"},
            "output_preview": "README content",
            "call_id": "call_1",
        }
    ]


def test_compact_message_output_falls_back_to_json():
    payload = {"id": "msg_1", "finish": "stop"}

    assert compact_message_output(payload) == json.dumps(payload, ensure_ascii=False, sort_keys=True)


def test_step_prompt_points_agent_at_skill_and_workdir():
    prompt = render_step_prompt(
        step={"input": "请生成 README.md"},
        paths={"skill_file": "/workspace/run/skill/SKILL.md", "workdir": "/workspace/run/workdir"},
        step_number=1,
        total_steps=2,
    )

    assert "/workspace/run/skill/SKILL.md" in prompt
    assert "/workspace/run/workdir" in prompt
    assert "不要写 result.json" in prompt
    assert "请生成 README.md" in prompt
