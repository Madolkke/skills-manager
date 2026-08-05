from __future__ import annotations

from skillhub.models.rules.workflows import normalize_collection_definition
from skillhub.models.rules.workflows.generators.documents import render_collection_reference, render_entry
from tests.executor_workflow_fixture import executor_workflow_document


def test_config_generator_uses_config_matching_language() -> None:
    document = executor_workflow_document()
    document["collectionSnapshots"][0]["spec"] = {
        "collectionType": "config",
        "config": {
            "commands": [
                {"name": "interface", "unique": False, "pattern": "interface <name>", "captures": {"name": {"type": "string", "title": "接口", "description": ""}}, "children": []}
            ]
        },
    }

    entry = render_entry(slug="config-workflow", document=document, reference_path="references/workflow.md", split_nodes=False)
    collection = render_collection_reference(normalize_collection_definition(document["collectionSnapshots"][0]))

    assert "配置匹配采集" in entry
    assert "执行器从设备完整配置中匹配以下命令块" in collection
    assert "interface" in collection
    assert "CLI 命令" not in entry
