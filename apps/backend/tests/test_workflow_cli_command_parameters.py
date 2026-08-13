from skillhub.models.rules.workflows.cli_command_parameters import parse_cli_command_parameters
from skillhub.models.rules.workflows.schema import normalize_collection_definition
from skillhub.models.rules.workflows.validation import validate_workflow_document


def test_angle_parameters_are_unique_and_support_unicode_identifiers():
    parsed = parse_cli_command_parameters("display interface <接口名> peer <peer_ip> <_private> <接口名>")

    assert parsed.error is None
    assert parsed.names == ("接口名", "peer_ip", "_private")


def test_invalid_angle_parameters_are_preserved_as_diagnostics():
    assert parse_cli_command_parameters("display <class>").error
    assert parse_cli_command_parameters("display <peer-ip>").error
    assert parse_cli_command_parameters("display <peer").error
    assert parse_cli_command_parameters("display peer>").error


def test_legacy_cli_definition_does_not_enable_angle_validation():
    definition = _definition()
    definition["spec"]["commandTemplate"] = "display <peer-ip>"

    normalized = normalize_collection_definition(definition)

    assert "commandParameterSyntax" not in normalized["spec"]


def test_enabled_cli_definition_requires_a_matching_input():
    definition = _definition()
    definition["spec"].update(commandTemplate="display <peer_ip>", commandParameterSyntax="angle-v1")
    document = {
        "documentType": "workflow_bundle",
        "workflow": {
            "id": "workflow-1",
            "revision": 1,
            "metadata": {"name": "测试", "code": "", "description": "测试", "symptom": "", "industry": "", "device": "", "versions": []},
            "inputs": [],
            "deviceRoles": [],
            "nodes": [],
        },
        "collectionSnapshots": [definition],
    }

    issues = validate_workflow_document(document)

    assert "CLI_COMMAND_PARAMETER_INPUT_MISSING" in {item["code"] for item in issues}


def _definition():
    return {
        "id": "collection-1",
        "revision": 1,
        "key": "status",
        "metadata": {"name": "状态", "description": "", "industry": "", "device": "", "versions": [], "tags": []},
        "spec": {"collectionType": "cli", "commandTemplate": "display status", "outputSamples": []},
        "inputs": [],
        "outputs": [],
    }
