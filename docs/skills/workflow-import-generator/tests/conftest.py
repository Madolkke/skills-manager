"""Skill 测试只加载纯规则，不需要数据库或网络。"""
import json
import sys
from pathlib import Path

import pytest

SKILL = Path(__file__).parents[1]
sys.path.insert(0, str(SKILL / "scripts"))
sys.path.insert(0, str(SKILL.parents[2] / "apps" / "backend"))


@pytest.fixture
def bundle():
    """每个测试使用独立的完整 CLI 示例副本。"""
    return json.loads((SKILL / "tests/fixtures/complex-cli.workflow-import.json").read_text(encoding="utf-8"))


@pytest.fixture
def check(tmp_path):
    """运行真实离线入口，并确认输入字节保持不变。"""
    from validate_workflow_import_bundle import validate

    def run(bundle, mode="strict", contract=None):
        path = tmp_path / "bundle.json"
        path.write_text(json.dumps(bundle, ensure_ascii=False), encoding="utf-8")
        before = path.read_bytes()
        contract_path = None
        if contract is not None:
            contract_path = tmp_path / "contract.json"
            contract_path.write_text(json.dumps(contract), encoding="utf-8")
        result = validate(path, mode=mode, contract_path=contract_path)
        assert path.read_bytes() == before
        return result

    return run
