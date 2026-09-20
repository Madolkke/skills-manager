"""校验现有纯规则与 CLI Skill 范围，不依赖诊断文案。"""
from copy import deepcopy

import pytest


def codes(report):
    """汇总机器诊断供行为断言。"""
    return {d["code"] for d in report["diagnostics"] + report["expressionDiagnostics"] + report["hardErrors"]}


def test_complete_cli_bundle_and_no_external_effects(bundle, check, monkeypatch):
    """复杂绑定和模板严格通过，任何连接或执行尝试都会使测试失败。"""
    import socket
    import subprocess

    import sqlalchemy

    def forbidden(*args, **kwargs):
        raise AssertionError("离线校验不能连接或执行")
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(sqlalchemy, "create_engine", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    result = check(bundle)
    assert result["passed"] and result["staticValid"] and result["importChecksPassed"]
    assert result["diagnostics"] == result["expressionDiagnostics"] == []


def test_draft_vs_strict_and_location(bundle, check):
    """空命令不阻止草稿，严格模式拒绝且报告 localId。"""
    bundle["collections"][3]["spec"]["commandTemplate"] = ""
    draft, strict = check(bundle, "draft"), check(bundle)
    assert draft["passed"] and not draft["staticValid"]
    assert not strict["passed"] and strict["importChecksPassed"]
    item = next(d for d in strict["diagnostics"] if d["code"] == "MISSING_COLLECTION_COMMAND")
    assert item["location"] == {"localId": "fabric", "field": "spec.commandTemplate"}
    assert len(draft["placeholders"]) == 1


def test_duplicate_placeholders_and_fixed_command(bundle, check):
    """同名占位符只需一个输入，固定命令不得复制多余输入。"""
    bundle["collections"][1]["spec"]["commandTemplate"] = "show routes <vrf> compare <vrf>"
    assert check(bundle)["passed"]
    bundle["collections"][1]["inputs"].append(deepcopy(bundle["collections"][1]["inputs"][0]))
    assert "DUPLICATE_COLLECTION_INPUT_ID" in codes(check(bundle))
    bundle["collections"][3]["inputs"] = [deepcopy(bundle["collections"][0]["inputs"][0])]
    assert "SKILL_UNUSED_COMMAND_INPUT" in codes(check(bundle))


@pytest.mark.parametrize("command,expected", [("show <vrf", "CLI_COMMAND_PARAMETER_SYNTAX_INVALID"),
                                             ("show <other>", "CLI_COMMAND_PARAMETER_INPUT_MISSING")])
def test_bad_command_parameters(bundle, check, command, expected):
    """命令错误沿用后端错误码。"""
    bundle["collections"][1]["spec"]["commandTemplate"] = command
    assert expected in codes(check(bundle))


@pytest.mark.parametrize("mutation,code,hard", [
    ("duplicate", "DUPLICATE_NODE_ID", False), ("no-start", "NO_START_STEP", False),
    ("multi-start", "SKILL_MULTIPLE_START_STEPS", False), ("target", "SKILL_IMPORT_REJECTED", True),
    ("missing-definition", "SKILL_IMPORT_REJECTED", True), ("duplicate-local", "SKILL_IMPORT_REJECTED", True),
])
def test_topology_and_references(bundle, check, mutation, code, hard):
    """区分作者完整性和后端导入硬限制。"""
    nodes = bundle["workflow"]["nodes"]
    if mutation == "duplicate":
        nodes.append(deepcopy(nodes[-1]))
    elif mutation == "no-start":
        nodes[0]["isStart"] = False
    elif mutation == "multi-start":
        nodes[1]["isStart"] = True
    elif mutation == "target":
        nodes[0]["topology"][0]["target"]["id"] = "missing"
    elif mutation == "missing-definition":
        nodes[0]["collectionCalls"][0]["definitionLocalId"] = "missing"
    else:
        bundle["collections"].append(deepcopy(bundle["collections"][0]))
    result = check(bundle)
    assert not result["passed"] and code in codes(result)
    assert result["importChecksPassed"] is not hard


@pytest.mark.parametrize("expression", ["outputs.routes.routes[0].next_hops[0].weight", "outputs.fabric[0].labels[0]"])
def test_binding_type_and_forward_scope_are_hard_failures(bundle, check, expression):
    """number 不能绑定 string，前序调用不能读取后续步骤。"""
    bundle["workflow"]["nodes"][0]["collectionCalls"][2]["inputBindings"]["input-vrf"]["expression"] = expression
    result = check(bundle, "draft")
    assert not result["passed"] and not result["importChecksPassed"]
    assert "SKILL_IMPORT_REJECTED" in codes(result)
    located = [d["location"] for d in result["diagnostics"] if d["location"].get("callId") == "call-bgp"]
    assert any(d.get("localId") == "bgp" for d in located)


@pytest.mark.parametrize("path", ["outputs.fabric[-1].matrix[0][0].healthy", "outputs.fabric[inputs.index].matrix[0][0].healthy"])
def test_array_indexes(bundle, check, path):
    """负数与动态整数下标按后端规则检查。"""
    bundle["workflow"]["nodes"][1]["topology"][0]["conditionExpression"] = path
    assert check(bundle)["passed"]


def test_known_sample_bound_warning_preserved(bundle, check):
    """已知采集越界维持 warning，不因严格模式被统一升级。"""
    bundle["workflow"]["nodes"][1]["topology"][0]["conditionExpression"] = "outputs.fabric[3].matrix[0][0].healthy"
    result = check(bundle)
    assert result["passed"]
    assert any(d["severity"] == "warning" for d in result["diagnostics"])
    assert result["expressionDiagnostics"][0]["start"] >= 0


@pytest.mark.parametrize("expression", ["sum(1) > 0", "sum(['x']) > 0", "len(1) > 0", "missing_function()"])
def test_functions_rejected_even_in_draft(bundle, check, expression):
    """非法调用由现有静态签名拒绝而非执行函数。"""
    bundle["workflow"]["nodes"][0]["topology"][0]["conditionExpression"] = expression
    result = check(bundle, "draft")
    assert not result["passed"] and any(c.startswith("FUNCTION_") or c == "UNREGISTERED_CALL" for c in codes(result))


def test_template_diagnostic_keeps_position(bundle, check):
    """模板错误保留字段、跳转与 UTF-16 位置。"""
    bundle["workflow"]["nodes"][0]["topology"][0]["conditionText"] = "接口 {{ len(1) }}"
    result = check(bundle)
    item = next(d for d in result["expressionDiagnostics"] if d["code"].startswith("FUNCTION_"))
    assert item["location"]["transitionId"] == "to-fabric"
    assert item["location"]["field"] == "conditionText" and item["end"] > item["start"]
    assert not result["passed"]


@pytest.mark.parametrize("field", ["sourceSystemCommandId", "sourceBindingMode", "source_system_command_id", "forkedFrom"])
def test_source_and_persistent_fields_rejected(bundle, check, field):
    """可移植 Bundle 不接受本地来源关联。"""
    bundle["collections"][0][field] = "local"
    result = check(bundle, "draft")
    assert not result["passed"] and "SKILL_PERSISTENT_FIELD" in codes(result)


def test_non_cli_is_rejected(bundle, check):
    """合法函数 Collection 也超出本 Skill 范围。"""
    bundle["collections"][0]["spec"] = {"collectionType": "function", "language": "python", "source": "raise RuntimeError('must not run')"}
    result = check(bundle, "draft")
    assert not result["passed"] and "SKILL_CLI_ONLY" in codes(result)


@pytest.mark.parametrize("spec", [
    {"collectionType": "log", "sqlDialect": "duckdb", "queries": [], "outputSamples": []},
    {"collectionType": "config", "config": {"commands": []}},
])
def test_other_collection_types_are_rejected(bundle, check, spec):
    """日志和配置即使结构合法也不会作为 CLI 自动降级。"""
    bundle["collections"][0]["spec"] = spec
    assert "SKILL_CLI_ONLY" in codes(check(bundle, "draft"))


@pytest.mark.parametrize("schema", [
    {"type": "array"},
    {"type": "object", "properties": {}, "required": ["missing"], "additionalProperties": False},
])
def test_malformed_output_schema_is_not_a_draft(bundle, check, schema):
    """非法数组或 required 不能伪装成可导入草稿。"""
    bundle["collections"][0]["outputs"][0]["schema"] = schema
    report = check(bundle, "draft")
    assert not report["passed"] and "SKILL_STRUCTURE_INVALID" in codes(report)


def test_script_step_source_is_only_text(bundle, check, tmp_path):
    """即使提供会写文件的脚本源码，离线校验也只处理文本。"""
    marker = tmp_path / "must-not-exist"
    node = bundle["workflow"]["nodes"][0]
    node["stepType"] = "script"
    node["script"] = {"language": "python", "source": f"open({str(marker)!r}, 'w').write('executed')", "options": {}}
    result = check(bundle)
    assert result["passed"] and not marker.exists()
