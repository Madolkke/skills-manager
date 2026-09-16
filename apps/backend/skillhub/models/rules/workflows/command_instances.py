"""具体命令的参数同步和来源投影；不执行设备命令。"""
from copy import deepcopy
from typing import Any

from skillhub.models.errors import InvariantError
from skillhub.models.rules.command_expression import match_command_expression

from .cli_command_parameters import parse_cli_command_parameters
from .command_projection import _source_to_collection
from .validation_helpers import issue


def set_instance_command(definition: dict[str, Any], command: str) -> dict[str, Any]:
    """按实际占位符同步输入，保留同名参数身份和类型。"""
    parsed = parse_cli_command_parameters(command)
    if not command.strip() or "\n" in command or "\r" in command or parsed.error:
        raise InvariantError(parsed.error or "具体采集命令必须为非空单行。")
    candidate = deepcopy(definition)
    existing = {item["key"]: item for item in candidate["inputs"]}
    used_ids = {item["id"] for item in existing.values()}
    inputs = []
    for name in parsed.names:
        if name in existing:
            inputs.append(existing[name])
            continue
        input_id = f"input_{name}"
        while input_id in used_ids:
            input_id += "_"
        used_ids.add(input_id)
        inputs.append({"id": input_id, "key": name, "required": True,
                       "schema": {"type": "string", "title": name, "description": ""}})
    candidate["inputs"] = inputs
    candidate["spec"].update(commandTemplate=command, commandParameterSyntax="angle-v1")
    for sample in candidate["spec"].get("outputSamples", []):
        sample["inputValues"] = {key: value for key, value in sample.get("inputValues", {}).items() if key in parsed.names}
    if candidate.get("sourceSystemCommandId"):
        candidate["sourceBindingMode"] = "concrete-command"
    return candidate


def project_instance_source(source: Any, current: dict[str, Any], *, revision: int) -> dict[str, Any]:
    """来源控制展示与输出字段，实例保留命令、输入和副本身份。"""
    projected = _source_to_collection(source, definition_id=current["id"], revision=revision, source_id=current["sourceSystemCommandId"])
    if current.get("sourceBindingMode") != "concrete-command":
        return projected
    normalized = set_instance_command(current, current["spec"]["commandTemplate"])
    if normalized["inputs"] != current["inputs"]:
        raise InvariantError("具体命令的输入参数必须与占位符一致。")
    projected.update(key=current["key"], inputs=deepcopy(current["inputs"]),
                     forkedFrom=current.get("forkedFrom"), sourceBindingMode="concrete-command")
    if not projected.get("forkedFrom"):
        projected.pop("forkedFrom", None)
    projected["spec"].update(commandTemplate=current["spec"]["commandTemplate"], commandParameterSyntax="angle-v1")
    return projected


def instantiate_command(source: Any, command: str, *, definition_id: str) -> dict[str, Any]:
    """新实例不继承表达式捕获参数，参数完全来自具体命令。"""
    if not source.enabled:
        raise InvariantError("系统命令已停用，不能创建新实例。")
    definition = _source_to_collection(source, definition_id=definition_id, revision=1, source_id=source.id)
    definition["inputs"] = []
    return set_instance_command(definition, command)


def command_match_warnings(definition: dict[str, Any], expression: str) -> list[dict[str, Any]]:
    """匹配仅提供提醒，动态参数不会被伪造为运行值。"""
    if definition.get("sourceBindingMode") != "concrete-command":
        return []
    command = definition["spec"]["commandTemplate"]
    parsed = parse_cli_command_parameters(command)
    if parsed.error:
        return []
    code, message = "", ""
    if parsed.names:
        code, message = "COMMAND_MATCH_DYNAMIC", "含动态参数，无法确认运行时匹配；请确认来源回显 Schema 适用。"
    else:
        try:
            matches = match_command_expression(expression, command)
        except InvariantError:
            matches = None
        if matches is None:
            code, message = "COMMAND_SOURCE_MISMATCH", "具体命令不匹配来源表达式；请确认来源回显 Schema 适用。"
    if not code:
        return []
    warning = issue(code, "warning", message, {"type": "collection", "id": definition["id"], "field": "spec.commandTemplate"})
    warning["id"] = f"{code}:{definition['id']}"
    return [warning]
