"""离线校验 CLI Import Bundle；只读输入，无网络、数据库和执行副作用。"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from offline_contract import read_contract
from offline_diagnostics import expression_diagnostics, locate


def repository_root(script_path: Path) -> Path:
    """定位后端源码，沿用 Skill 的仓库内运行方式。"""
    for parent in script_path.resolve().parents:
        if (parent / "apps" / "backend" / "skillhub").is_dir():
            return parent
    raise RuntimeError("未找到 apps/backend/skillhub，请在完整仓库中使用此 Skill。")


def diagnostic(code: str, message: str, **location) -> dict:
    """生成脚本自身的硬性失败诊断，不冒充后端错误码。"""
    return {"code": code, "severity": "error", "message": message, "location": location}


def forbidden_fields(raw: dict) -> list[dict]:
    """检查可移植文件禁止携带的数据库身份及来源关联。"""
    errors = []
    workflow = raw.get("workflow", {})
    if isinstance(workflow, dict):
        for field in ("id", "revision"):
            if field in workflow:
                errors.append(diagnostic("SKILL_PERSISTENT_FIELD", f"workflow 不允许包含持久化字段: {field}", field=f"workflow.{field}"))
    definitions = raw.get("collections", [])
    for definition in definitions if isinstance(definitions, list) else []:
        if not isinstance(definition, dict):
            continue
        for field in ("id", "revision", "forkedFrom", "forked_from", "sourceSystemCommandId", "source_system_command_id", "sourceBindingMode", "source_binding_mode"):
            if field in definition:
                errors.append(diagnostic("SKILL_PERSISTENT_FIELD", f"Collection 不允许包含本地身份或来源字段: {field}",
                                         localId=definition.get("localId", definition.get("local_id")), field=field))
    return errors


def skill_issues(bundle: dict) -> list[dict]:
    """本 Skill 的生成约束单独标记，不改变后端的草稿与提醒语义。"""
    from skillhub.models.rules.workflows.cli_command_parameters import parse_cli_command_parameters

    issues = []
    starts = [n for n in bundle["workflow"]["nodes"] if n.get("isStart")]
    if len(starts) > 1:
        issues.append(diagnostic("SKILL_MULTIPLE_START_STEPS", "本 Skill 的完整生成结果要求恰有一个起始步骤。", field="workflow.nodes.isStart"))
    for definition in bundle["collections"]:
        spec = definition["spec"]
        if spec.get("commandParameterSyntax") != "angle-v1" or not spec["commandTemplate"].strip():
            continue
        parsed = parse_cli_command_parameters(spec["commandTemplate"])
        if not parsed.error:
            for parameter in definition["inputs"]:
                if parameter["key"] not in parsed.names:
                    issues.append(diagnostic("SKILL_UNUSED_COMMAND_INPUT", "具体命令没有引用该输入，请删除多余输入及对应绑定。",
                                             localId=definition["localId"], itemId=parameter["id"], field="inputs"))
    return issues


def validate(bundle_path: Path, *, mode: str = "draft", contract_path: Path | None = None) -> dict:
    """返回完整机器报告；draft 仅放宽后端允许的领域错误，不放宽导入硬限制。"""
    sys.path.insert(0, str(repository_root(Path(__file__)) / "apps" / "backend"))
    from skillhub.models.errors import InvariantError
    from skillhub.models.rules.workflows import (
        materialize_workflow_import, normalize_collection_definition, normalize_workflow_document,
        normalize_workflow_import_bundle, validate_workflow_document, validate_workflow_import_references,
    )

    report = {"mode": mode, "passed": False, "status": "invalid", "importChecksPassed": False,
              "staticValid": False, "contract": None, "hardErrors": [], "diagnostics": [],
              "expressionDiagnostics": [], "placeholders": []}
    try:
        functions, report["contract"] = read_contract(contract_path)
    except (OSError, ValueError, InvariantError) as exc:
        report["hardErrors"].append(diagnostic("SKILL_CONTRACT_INVALID", str(exc)))
        return report
    try:
        raw = json.loads(bundle_path.read_text(encoding="utf-8-sig"))
        if not isinstance(raw, dict):
            raise ValueError("导入 Bundle 根节点必须是 JSON 对象。")
    except (OSError, ValueError) as exc:
        report["hardErrors"].append(diagnostic("SKILL_INPUT_INVALID", str(exc)))
        return report
    report["hardErrors"].extend(forbidden_fields(raw))
    if report["hardErrors"]:
        return report
    try:
        bundle = normalize_workflow_import_bundle(raw)
    except (InvariantError, ValueError, TypeError, KeyError, AttributeError) as exc:
        report["hardErrors"].append(diagnostic("SKILL_STRUCTURE_INVALID", str(exc)))
        return report
    for definition in bundle["collections"]:
        if definition["spec"]["collectionType"] != "cli":
            report["hardErrors"].append(diagnostic("SKILL_CLI_ONLY", "此 Skill 仅支持 CLI 采集。", localId=definition["localId"]))
        elif not definition["spec"]["commandTemplate"].strip():
            report["placeholders"].append({"localId": definition["localId"], "name": definition["metadata"]["name"]})
    if report["hardErrors"]:
        return report
    try:
        validate_workflow_import_references(bundle, functions)
    except InvariantError as exc:
        report["hardErrors"].append(diagnostic("SKILL_IMPORT_REJECTED", str(exc)))
    try:
        mappings = {d["localId"]: (d["localId"], 1) for d in bundle["collections"]}
        document = materialize_workflow_import(bundle, workflow_id="offline-validation", revision=1, collection_mappings=mappings)
        document["collectionSnapshots"] = [normalize_collection_definition({
            **{k: v for k, v in d.items() if k != "localId"}, "id": d["localId"], "revision": 1,
        }) for d in bundle["collections"]]
        document = normalize_workflow_document(document)
        report["diagnostics"] = [locate(d, bundle) for d in validate_workflow_document(document, functions)]
        report["diagnostics"].extend(skill_issues(bundle))
        report["expressionDiagnostics"] = [locate(d, bundle) for d in expression_diagnostics(document, functions)]
    except (InvariantError, KeyError) as exc:
        if not report["hardErrors"]:
            report["hardErrors"].append(diagnostic("SKILL_PROJECTION_INVALID", str(exc)))
    report["importChecksPassed"] = not report["hardErrors"]
    report["staticValid"] = report["importChecksPassed"] and not any(
        d["severity"] == "error" for d in [*report["diagnostics"], *report["expressionDiagnostics"]])
    report["passed"] = report["importChecksPassed"] and (mode == "draft" or report["staticValid"])
    report["status"] = "invalid" if not report["importChecksPassed"] else "valid" if report["staticValid"] else "draft"
    return report


def main() -> int:
    """提供中文摘要和可选 JSON 报告，失败时不覆盖输入或契约文件。"""
    parser = argparse.ArgumentParser(description="离线校验 CLI WorkflowImportBundle（不执行或导入）")
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--mode", choices=("draft", "strict"), default="draft")
    parser.add_argument("--expression-contract", type=Path)
    parser.add_argument("--report-json", type=Path)
    args = parser.parse_args()
    protected = [args.bundle, args.expression_contract, Path(__file__), *Path(__file__).parent.glob("*.py")]
    if args.report_json and any(p and args.report_json.resolve() == p.resolve() for p in protected):
        print("报告路径不得覆盖 Bundle、表达式契约或校验脚本。", file=sys.stderr)
        return 1
    try:
        report = validate(args.bundle, mode=args.mode, contract_path=args.expression_contract)
        if args.report_json:
            args.report_json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except (OSError, RuntimeError, ImportError) as exc:
        print(f"校验环境或报告写入失败: {exc}", file=sys.stderr)
        return 1
    if report["importChecksPassed"]:
        print("Bundle 结构和引用校验通过。")
    if report["placeholders"]:
        print(f"草稿含 {len(report['placeholders'])} 个未配置命令的 CLI 占位 Collection。")
    for item in report["hardErrors"] + report["diagnostics"]:
        print(f"[{item['severity']}] {item['code']}: {item['message']} {item['location']}")
    for item in report["expressionDiagnostics"]:
        print(f"[表达式 {item['severity']}] {item['code']}: {item['message']} {item['location']} [{item['start']}:{item['end']}]")
    print(f"模式={args.mode}；结果={report['status']}；通过={report['passed']}。静态校验不证明命令可执行。")
    if report["contract"]:
        print(f"函数契约来源：{report['contract']['source']}。{report['contract']['notice']}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
