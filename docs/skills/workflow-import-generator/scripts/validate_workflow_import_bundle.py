from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def repository_root(script_path: Path) -> Path:
    """定位包含 SkillHub 后端源码的仓库根目录。"""
    for parent in script_path.resolve().parents:
        if (parent / "apps" / "backend" / "skillhub").is_dir():
            return parent
    raise RuntimeError("未找到 apps/backend/skillhub，无法加载导入 Bundle 校验器。")


def import_validators(repo_root: Path):
    """从当前仓库的后端加载 Bundle 标准化和引用校验函数。"""
    backend_path = repo_root / "apps" / "backend"
    sys.path.insert(0, str(backend_path))
    from skillhub.models.rules.workflows import normalize_workflow_import_bundle, validate_workflow_import_references

    return normalize_workflow_import_bundle, validate_workflow_import_references


def persistent_field_errors(bundle: dict[str, Any]) -> list[str]:
    """列出 Import Bundle 中不允许携带的持久化字段。"""
    errors: list[str] = []
    workflow = bundle.get("workflow")
    if isinstance(workflow, dict):
        for field in ("id", "revision"):
            if field in workflow:
                errors.append(f"workflow 不允许包含持久化字段: {field}")
    collections = bundle.get("collections")
    if isinstance(collections, list):
        for index, definition in enumerate(collections):
            if not isinstance(definition, dict):
                continue
            label = str(definition.get("localId") or index)
            for field in ("id", "revision", "forkedFrom"):
                if field in definition:
                    errors.append(f"Collection {label} 不允许包含持久化字段: {field}")
    return errors


def cli_placeholders(bundle: dict[str, Any]) -> list[tuple[str, str]]:
    """找出结构合法但尚未配置执行命令的 CLI 定义。"""
    result: list[tuple[str, str]] = []
    for definition in bundle.get("collections", []):
        spec = definition.get("spec", {})
        if spec.get("collectionType") != "cli" or spec.get("commandTemplate", "").strip():
            continue
        result.append((definition["localId"], definition["metadata"]["name"]))
    return result


def validate(bundle_path: Path) -> list[tuple[str, str]]:
    """执行结构、禁止字段和 Collection 引用校验，并返回 CLI 占位项。"""
    raw = json.loads(bundle_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("导入 Bundle 根节点必须是 JSON 对象。")
    errors = persistent_field_errors(raw)
    if errors:
        raise ValueError("\n".join(errors))
    normalize, validate_references = import_validators(repository_root(Path(__file__)))
    normalized = normalize(raw)
    validate_references(normalized)
    return cli_placeholders(normalized)


def main() -> int:
    """解析命令行参数并输出可操作的校验结论。"""
    parser = argparse.ArgumentParser(description="校验 SkillHub WorkflowImportBundle")
    parser.add_argument("bundle", type=Path, help="WorkflowImportBundle JSON 文件")
    args = parser.parse_args()
    try:
        placeholders = validate(args.bundle)
    except (OSError, ValueError, json.JSONDecodeError, RuntimeError) as exc:
        print(f"校验失败: {exc}", file=sys.stderr)
        return 1
    print("Bundle 结构和引用校验通过。")
    if placeholders:
        print(f"可导入草稿，含 {len(placeholders)} 个未配置命令的 CLI 占位 Collection：")
        for local_id, name in placeholders:
            print(f"- {local_id}: {name}")
        print("补全 commandTemplate 及必要的输入/输出 Schema 后，才能同步执行。")
    else:
        print("未检测到 CLI 执行占位项。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
