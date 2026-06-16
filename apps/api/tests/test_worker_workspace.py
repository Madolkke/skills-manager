from __future__ import annotations

import base64
import io
import json
from pathlib import Path
import zipfile

import pytest

from skillhub_worker.workspace import read_runner_result, _extract_zip_to_workdir


def zip_payload(files: dict[str, str]) -> str:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for path, content in files.items():
            archive.writestr(path, content)
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def test_extract_zip_rejects_path_traversal(tmp_path: Path):
    with pytest.raises(RuntimeError, match="Unsafe zip path"):
        _extract_zip_to_workdir(zip_payload({"../escape.txt": "bad"}), tmp_path)


def test_extract_zip_copies_files_to_workdir(tmp_path: Path):
    _extract_zip_to_workdir(zip_payload({"docs/input.txt": "hello"}), tmp_path)

    assert (tmp_path / "docs" / "input.txt").read_text(encoding="utf-8") == "hello"


def test_read_runner_result_requires_structured_json(tmp_path: Path):
    path = tmp_path / "result.json"
    path.write_text(json.dumps({"passed": False, "actual_output": "missed", "reason": "wrong"}), encoding="utf-8")

    assert read_runner_result(str(path)) == {"passed": False, "actual_output": "missed", "reason": "wrong"}


def test_read_runner_result_rejects_invalid_payload(tmp_path: Path):
    path = tmp_path / "result.json"
    path.write_text(json.dumps({"passed": "yes", "actual_output": "bad"}), encoding="utf-8")

    with pytest.raises(RuntimeError, match="boolean passed"):
        read_runner_result(str(path))
