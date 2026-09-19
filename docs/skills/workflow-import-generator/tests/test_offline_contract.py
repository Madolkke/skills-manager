"""本地函数声明的替换、启停、顺序与错误边界。"""
import json

import pytest

from conftest import SKILL
from test_validate_workflow_import_bundle import validate_with_script


def contract(functions):
    """构造公开契约格式，显式空目录不回退。"""
    return {"contractVersion": 1, "language": "python-eval", "functions": functions}


def test_custom_function_order_and_no_body_execution(bundle, check):
    """参数顺序与 Schema 复用函数库规则，函数体不会执行或进入报告。"""
    from skillhub.models.rules.workflows.expression.registry import expression_contract

    catalog = expression_contract()
    catalog["functions"]["custom_check"] = {
        "parameterSchema": {"type": "object", "properties": {"a": {"type": "integer"}, "z": {"type": "string"}},
                            "required": ["a", "z"], "additionalProperties": False, "x-parameter-order": ["z", "a"]},
        "returnSchema": {"type": "boolean"}, "body": "raise RuntimeError('never-execute-sentinel')",
    }
    transition = bundle["workflow"]["nodes"][0]["topology"][0]
    transition["conditionExpression"] = "custom_check('value', 1)"
    report = check(bundle, contract=catalog)
    assert report["passed"] and "never-execute-sentinel" not in json.dumps(report)
    transition["conditionExpression"] = "custom_check(1, 'value')"
    assert not check(bundle, contract=catalog)["passed"]


def test_empty_and_disabled_catalogs_do_not_fallback(bundle, check):
    """显式空目录和停用记录都应拒绝示例中的 len。"""
    empty = check(bundle, contract=contract({}))
    disabled = check(bundle, contract=contract({"len": {"legacyBuiltin": True, "enabled": False}}))
    assert not empty["passed"] and not disabled["passed"]
    assert any(d["code"] == "UNREGISTERED_CALL" for d in empty["diagnostics"])


@pytest.mark.parametrize("raw", [[], {}, {"contractVersion": 2}, contract([]),
    contract({"bad-name": {}}), contract({"new_builtin": {"legacyBuiltin": True}}),
    contract({"len": {"legacyBuiltin": True, "isBuiltin": False}}),
    contract({"len": {"enabled": "true"}}),
    contract({"custom": {"parameterSchema": {"type": "array"}, "returnSchema": {"type": "integer"}}}),
    contract({"custom": {"parameterSchema": {"type": "object", "properties": {}, "required": ["missing"]}, "returnSchema": {"type": "integer"}}}),
])
def test_malformed_contract_is_hard_error(bundle, check, raw):
    """非法契约不能被忽略并静默使用默认函数目录。"""
    result = check(bundle, "draft", contract=raw)
    assert not result["passed"] and result["hardErrors"][0]["code"] == "SKILL_CONTRACT_INVALID"


def test_cli_json_report_and_input_protection(tmp_path):
    """真实命令行返回码、机器报告及路径保护可观测。"""
    import subprocess
    import sys

    script = SKILL / "scripts/validate_workflow_import_bundle.py"
    source = SKILL / "tests/fixtures/system-status-process.workflow-import.json"
    report = tmp_path / "report.json"
    result = subprocess.run([sys.executable, str(script), str(source), "--mode", "strict", "--report-json", str(report)], capture_output=True)
    assert result.returncode == 1
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["status"] == "draft" and payload["importChecksPassed"]
    before = source.read_bytes()
    result = subprocess.run([sys.executable, str(script), str(source), "--report-json", str(source)], capture_output=True)
    assert result.returncode == 1 and source.read_bytes() == before


@pytest.mark.parametrize("content", ["not json", "[]", '{"workflow": []}', '{"workflow": {"nodes": [null]}}'])
def test_bad_bundle_fails_without_traceback(tmp_path, content):
    """损坏输入提供可读失败而非异常堆栈。"""
    path = tmp_path / "bad.json"
    path.write_text(content, encoding="utf-8")
    result = validate_with_script(SKILL / "scripts/validate_workflow_import_bundle.py", path)
    assert result.returncode == 1 and "Traceback" not in result.stderr


def test_explicit_empty_catalog_accepts_function_free_workflow(bundle, check):
    """空目录只禁止函数，并不禁止无函数的 CLI 工作流。"""
    for node in bundle["workflow"]["nodes"]:
        for transition in node.get("topology", []):
            transition["conditionExpression"] = "True"
            transition["conditionText"] = "已完成采集"
        if node.get("nodeType") == "conclusion":
            node["rootCause"] = "人工查看采集结果"
    assert check(bundle, contract=contract({}))["passed"]
