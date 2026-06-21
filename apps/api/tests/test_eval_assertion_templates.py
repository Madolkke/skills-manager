from __future__ import annotations

from pathlib import Path

import pytest

from skillhub.application.eval_assertion_templates import AssertionContext, assertion_template, list_assertion_templates
from skillhub.domain.errors import InvariantError


def context(tmp_path: Path, *, output: str = "", before: set[str] | None = None, after: set[str] | None = None) -> AssertionContext:
    return AssertionContext(
        agent_output=output,
        workdir=tmp_path,
        before_snapshot=before or set(),
        after_snapshot=after or set(),
        step={"id": "step-1"},
        run_metadata={},
    )


def test_registry_returns_template_definitions():
    ids = {item["id"] for item in list_assertion_templates()}

    assert "agent_output_exact" in ids
    assert "file_created" in ids


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
