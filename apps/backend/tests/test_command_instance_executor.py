"""具体实例继续使用原执行器 DTO，命令和参数不回退到系统规则。"""
from skillhub.models.rules.executor_workflows import convert_workflow_document
from skillhub.models.rules.workflows.command_instances import set_instance_command
from skillhub.models.rules.workflows.schema import normalize_workflow_document
from tests.executor_workflow_fixture import executor_workflow_document


def test_scalar_instance_projects_actual_command_and_own_inputs():
    """覆盖固定实例与动态实例；保持既有 DTO 字段。"""
    document = normalize_workflow_document(executor_workflow_document())
    source = document["collectionSnapshots"][0]
    source["sourceSystemCommandId"] = "source-rule"
    call = document["workflow"]["nodes"][0]["collectionCalls"][0]
    for command in ("show routes default", "show routes <tenant>"):
        definition = set_instance_command(source, command)
        document["collectionSnapshots"][0] = definition
        call["inputBindings"] = {item["id"]: {"kind": "literal", "reference": {}, "value": "default"} for item in definition["inputs"]}
        result = convert_workflow_document(document)
        projected = result.steps[0].collections[0]
        assert projected.command == command
        assert [item.name for item in projected.inputs] == [item["key"] for item in definition["inputs"]]
        assert "sourceBindingMode" not in result.model_dump_json()
        assert "sourceSystemCommandId" not in result.model_dump_json()
