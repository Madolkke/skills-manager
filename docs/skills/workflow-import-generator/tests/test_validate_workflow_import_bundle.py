from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def validate_with_script(script: Path, bundle: Path) -> subprocess.CompletedProcess[str]:
    """通过 Skill 自带脚本执行 Bundle 校验。"""
    return subprocess.run(
        [sys.executable, str(script), str(bundle)],
        check=False,
        capture_output=True,
        encoding="utf-8",
    )


def test_placeholder_bundle_passes_structure_validation() -> None:
    """验证文档生成的占位 Bundle 可通过导入前结构校验。"""
    skill_dir = Path(__file__).parents[1]
    bundle = skill_dir / "tests" / "fixtures" / "system-status-process.workflow-import.json"
    script = skill_dir / "scripts" / "validate_workflow_import_bundle.py"

    result = validate_with_script(script, bundle)

    assert result.returncode == 0, result.stderr
    assert "Bundle 结构和引用校验通过。" in result.stdout
    assert "1 个未配置命令的 CLI 占位 Collection" in result.stdout


def test_existing_example_and_fixture_omit_persistent_fields() -> None:
    """验证正式示例和文档夹具均使用可移植导入字段。"""
    skill_dir = Path(__file__).parents[1]
    repo_root = skill_dir.parents[2]
    script = skill_dir / "scripts" / "validate_workflow_import_bundle.py"
    bundles = [
        repo_root / "docs" / "examples" / "executor-integration-workflow-import.json",
        skill_dir / "tests" / "fixtures" / "system-status-process.workflow-import.json",
    ]

    for bundle_path in bundles:
        bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
        assert not {"id", "revision"}.intersection(bundle["workflow"])
        for definition in bundle["collections"]:
            assert not {"id", "revision", "forkedFrom"}.intersection(definition)
        result = validate_with_script(script, bundle_path)
        assert result.returncode == 0, result.stderr


def test_persistent_workflow_id_is_rejected(tmp_path: Path) -> None:
    """验证校验器拒绝不能出现在导入 Bundle 中的持久化 ID。"""
    skill_dir = Path(__file__).parents[1]
    source = skill_dir / "tests" / "fixtures" / "system-status-process.workflow-import.json"
    bundle = json.loads(source.read_text(encoding="utf-8"))
    bundle["workflow"]["id"] = "persisted-workflow"
    invalid_bundle = tmp_path / "invalid.workflow-import.json"
    invalid_bundle.write_text(json.dumps(bundle, ensure_ascii=False), encoding="utf-8")

    result = validate_with_script(skill_dir / "scripts" / "validate_workflow_import_bundle.py", invalid_bundle)

    assert result.returncode == 1
    assert "workflow 不允许包含持久化字段: id" in result.stderr
