from __future__ import annotations

from pathlib import Path

import pytest

from skillhub.models.rules.eval_assertion_templates import AssertionContext, assertion_template, list_assertion_templates, safe_workdir_path
from skillhub.models.errors import InvariantError


def context(tmp_path: Path, *, output: str = "", before: set[str] | None = None, after: set[str] | None = None) -> AssertionContext:
    return AssertionContext(
        agent_output=output,
        workdir=tmp_path,
        before_snapshot=before or set(),
        after_snapshot=after or set(),
        step={"id": "step-1"},
        run_metadata={},
    )


def opencode_context(tmp_path: Path) -> AssertionContext:
    return AssertionContext(
        agent_output="完成",
        workdir=tmp_path,
        before_snapshot=set(),
        after_snapshot=set(),
        step={"id": "step-1"},
        run_metadata={},
        reasoning_text="I should read README.md before answering.",
        tool_calls=[
            {
                "tool": "read",
                "status": "completed",
                "input": {"filePath": "README.md"},
                "output_preview": "README content",
                "call_id": "call_1",
            },
            {
                "tool": "bash",
                "status": "completed",
                "input": {"command": "ls"},
                "output_preview": "README.md",
                "call_id": "call_2",
            },
        ],
    )


def test_registry_returns_template_definitions():
    ids = {item["id"] for item in list_assertion_templates()}

    assert "agent_output_exact" in ids
    assert "file_created" in ids
    assert "tool_called" in ids
    assert "reasoning_contains" in ids


def test_agent_output_contains_passes_and_fails(tmp_path: Path):
    template = assertion_template("agent_output_contains")

    assert template.evaluate(context(tmp_path, output="created README.md"), {"text": "README.md"}).passed is True
    assert template.evaluate(context(tmp_path, output="nothing"), {"text": "README.md"}).passed is False


def test_file_created_compares_before_and_after_snapshots(tmp_path: Path):
    target = tmp_path / "docs" / "answer.txt"
    target.parent.mkdir()
    target.write_text("ok", encoding="utf-8")
    template = assertion_template("file_created")

    passed = template.evaluate(context(tmp_path, before=set(), after={"docs/answer.txt"}), {"directory": "docs", "filename": "answer.txt"})
    existing = template.evaluate(context(tmp_path, before={"docs/answer.txt"}, after={"docs/answer.txt"}), {"directory": "docs", "filename": "answer.txt"})

    assert passed.passed is True
    assert existing.passed is False


def test_file_template_rejects_path_traversal(tmp_path: Path):
    template = assertion_template("file_exists")

    with pytest.raises(InvariantError, match="Unsafe workdir path"):
        template.evaluate(context(tmp_path), {"directory": "..", "filename": "escape.txt"})


def test_safe_workdir_path_rejects_resolved_escape(tmp_path: Path):
    outside = tmp_path.parent / f"{tmp_path.name}-outside"
    outside.mkdir()
    link = tmp_path / "linked-outside"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("Symlink creation is unavailable in this environment.")

    with pytest.raises(InvariantError, match="Unsafe workdir path"):
        safe_workdir_path(tmp_path, "linked-outside", "secret.txt")


@pytest.mark.parametrize(
    "directory, filename",
    [
        ("safe", "..\\escape.txt"),
        ("C:", "escape.txt"),
        ("safe", "C:\\escape.txt"),
    ],
)
def test_file_template_rejects_windows_style_unsafe_paths(tmp_path: Path, directory: str, filename: str):
    template = assertion_template("file_exists")

    with pytest.raises(InvariantError, match="Unsafe workdir path"):
        template.evaluate(context(tmp_path), {"directory": directory, "filename": filename})


def test_file_content_similarity_uses_threshold(tmp_path: Path):
    path = tmp_path / "answer.txt"
    path.write_text("hello world", encoding="utf-8")
    template = assertion_template("file_content_similarity")

    assert template.evaluate(context(tmp_path), {"path": "answer.txt", "expected": "hello world", "threshold": 0.99}).passed is True
    assert template.evaluate(context(tmp_path), {"path": "answer.txt", "expected": "goodbye", "threshold": 0.9}).passed is False


def test_tool_called_template_uses_standardized_tool_calls(tmp_path: Path):
    template = assertion_template("tool_called")

    assert template.evaluate(opencode_context(tmp_path), {"tool": "read"}).passed is True
    assert template.evaluate(opencode_context(tmp_path), {"tool": "write"}).passed is False


def test_tool_not_called_template_fails_when_tool_was_used(tmp_path: Path):
    template = assertion_template("tool_not_called")

    assert template.evaluate(opencode_context(tmp_path), {"tool": "write"}).passed is True
    assert template.evaluate(opencode_context(tmp_path), {"tool": "read"}).passed is False


def test_tool_call_count_template_supports_operators(tmp_path: Path):
    template = assertion_template("tool_call_count")

    assert template.evaluate(opencode_context(tmp_path), {"tool": "read", "operator": "equals", "count": 1}).passed is True
    assert template.evaluate(opencode_context(tmp_path), {"tool": "read", "operator": "at_least", "count": 1}).passed is True
    assert template.evaluate(opencode_context(tmp_path), {"tool": "read", "operator": "at_most", "count": 0}).passed is False
    with pytest.raises(InvariantError, match="operator"):
        template.evaluate(opencode_context(tmp_path), {"tool": "read", "operator": "roughly", "count": 1})


def test_tool_call_input_contains_template_checks_serialized_input(tmp_path: Path):
    template = assertion_template("tool_call_input_contains")

    assert template.evaluate(opencode_context(tmp_path), {"tool": "read", "text": "README.md"}).passed is True
    assert template.evaluate(opencode_context(tmp_path), {"tool": "bash", "text": "README.md"}).passed is False


def test_reasoning_templates_check_reasoning_text(tmp_path: Path):
    contains = assertion_template("reasoning_contains")
    not_contains = assertion_template("reasoning_not_contains")

    assert contains.evaluate(opencode_context(tmp_path), {"text": "README.md"}).passed is True
    assert contains.evaluate(opencode_context(tmp_path), {"text": "database"}).passed is False
    assert not_contains.evaluate(opencode_context(tmp_path), {"text": "database"}).passed is True
    assert not_contains.evaluate(opencode_context(tmp_path), {"text": "README.md"}).passed is False
