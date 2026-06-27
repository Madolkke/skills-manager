from __future__ import annotations

import ast
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1] / "skillhub"


def test_backend_uses_only_view_service_model_top_level_layers() -> None:
    allowed = {"__init__.py", "__pycache__", "bootstrap", "models", "services", "views"}
    actual = {path.name for path in PACKAGE_ROOT.iterdir()}
    assert actual <= allowed


def test_legacy_layers_are_not_imported() -> None:
    forbidden = {
        "skillhub.api",
        "skillhub.application",
        "skillhub.domain",
        "skillhub.infrastructure",
        "skillhub.repositories",
    }
    assert _imports_under(PACKAGE_ROOT, forbidden) == []


def test_views_only_dependencies_imports_store() -> None:
    forbidden = {"skillhub.models.store"}
    violations = _imports_under(PACKAGE_ROOT / "views", forbidden)
    assert violations == ["views\\dependencies.py imports skillhub.models.store"] or violations == [
        "views/dependencies.py imports skillhub.models.store"
    ]


def test_services_do_not_depend_on_fastapi() -> None:
    assert _imports_under(PACKAGE_ROOT / "services", {"fastapi"}) == []


def test_services_do_not_bypass_store_for_data_access() -> None:
    forbidden = {"skillhub.models.operations", "skillhub.models.schema"}
    assert _imports_under(PACKAGE_ROOT / "services", forbidden) == []


def test_models_do_not_depend_on_upper_layers() -> None:
    forbidden = {"skillhub.bootstrap", "skillhub.services", "skillhub.views"}
    assert _imports_under(PACKAGE_ROOT / "models", forbidden) == []


def test_rules_do_not_depend_on_data_access() -> None:
    forbidden = {"skillhub.models.operations", "skillhub.models.schema", "skillhub.models.store"}
    assert _imports_under(PACKAGE_ROOT / "models" / "rules", forbidden) == []


def test_schema_does_not_depend_on_data_access() -> None:
    forbidden = {"skillhub.models.operations", "skillhub.models.store"}
    assert _imports_under(PACKAGE_ROOT / "models" / "schema", forbidden) == []


def test_services_use_store_not_repository_attribute() -> None:
    violations: list[str] = []
    for path in (PACKAGE_ROOT / "services").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr == "repository":
                violations.append(f"{path.relative_to(PACKAGE_ROOT)} uses .repository")
    assert violations == []


def _imports_under(root: Path, forbidden_modules: set[str]) -> list[str]:
    violations: list[str] = []
    for path in root.rglob("*.py"):
        for imported in _imported_modules(path):
            if any(imported == module or imported.startswith(f"{module}.") for module in forbidden_modules):
                violations.append(f"{path.relative_to(PACKAGE_ROOT)} imports {imported}")
    return violations


def _imported_modules(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
    return imported
