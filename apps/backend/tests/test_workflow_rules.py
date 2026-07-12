from __future__ import annotations

import json
from pathlib import Path
import re
import unittest

import yaml

from skillhub.models.errors import InvariantError
from skillhub.models.rules.workflows import (
    migrate_workflow_document,
    materialize_workflow_import,
    normalize_workflow_document,
    normalize_workflow_import_bundle,
    render_skill_markdown,
    validate_workflow_document,
    validate_workflow_import_references,
)


class WorkflowRulesTest(unittest.TestCase):
    def test_agent_guide_import_example_matches_schema(self):
        guide = Path(__file__).parents[3] / "docs" / "workflow-import-agent-guide.md"
        text = guide.read_text(encoding="utf-8")
        match = re.search(
            r"<!-- workflow-import-example:start -->\s*```json\s*(.*?)\s*```\s*<!-- workflow-import-example:end -->",
            text,
            re.DOTALL,
        )

        self.assertIsNotNone(match)
        bundle = normalize_workflow_import_bundle(json.loads(match.group(1)))
        validate_workflow_import_references(bundle)

    def test_import_bundle_normalizes_without_persistent_id_or_revision(self):
        bundle = normalize_workflow_import_bundle(self._import_bundle())

        self.assertEqual(bundle["documentType"], "workflow_import_bundle")
        self.assertNotIn("id", bundle["workflow"])
        self.assertNotIn("revision", bundle["workflow"])
        self.assertEqual(bundle["collections"][0]["localId"], "interface-status")
        validate_workflow_import_references(bundle)

    def test_import_bundle_rejects_duplicate_local_ids_and_broken_references(self):
        duplicate = self._import_bundle()
        duplicate["collections"].append(dict(duplicate["collections"][0]))
        with self.assertRaisesRegex(InvariantError, "localId"):
            validate_workflow_import_references(normalize_workflow_import_bundle(duplicate))

        broken = self._import_bundle()
        broken["workflow"]["nodes"][0]["collectionCalls"][0]["definitionLocalId"] = "missing"
        with self.assertRaisesRegex(InvariantError, "does not exist"):
            validate_workflow_import_references(normalize_workflow_import_bundle(broken))

    def test_import_bundle_rejects_invalid_binding_reference(self):
        bundle = self._import_bundle()
        call = bundle["workflow"]["nodes"][0]["collectionCalls"][0]
        call["inputBindings"]["collection-input-interface"]["reference"]["input_id"] = "missing"

        with self.assertRaisesRegex(InvariantError, "Binding reference"):
            validate_workflow_import_references(normalize_workflow_import_bundle(bundle))

    def test_import_bundle_materializes_target_identity_and_collection_references(self):
        bundle = normalize_workflow_import_bundle(self._import_bundle())

        document = materialize_workflow_import(
            bundle,
            workflow_id="workflow-target",
            revision=7,
            collection_mappings={"interface-status": ("collection-generated", 1)},
        )

        self.assertEqual(document["workflow"]["id"], "workflow-target")
        self.assertEqual(document["workflow"]["revision"], 7)
        self.assertEqual(
            document["workflow"]["nodes"][0]["collectionCalls"][0]["definition"],
            {"id": "collection-generated", "revision": 1},
        )
        self.assertNotIn("definitionLocalId", document["workflow"]["nodes"][0]["collectionCalls"][0])

    def test_renderer_is_deterministic_and_uses_readable_binding_references(self):
        document = normalize_workflow_document(self._document())

        first = render_skill_markdown(slug="interface-check", document=document)
        second = render_skill_markdown(slug="interface-check", document=document)

        self.assertEqual(first, second)
        self.assertIn("全局输入 `interface_name` (接口名称)", first)
        self.assertNotIn("opaque-input-id", first)
        self.assertNotIn("opaque-parameter-id", first)
        self.assertNotIn("SECRET RAW OUTPUT", first)
        self.assertNotIn("SECRET INPUT VALUE", first)
        self.assertNotIn("- Key:", first)
        self.assertIn("接口 Down 示例", first)

    def test_renderer_safely_serializes_frontmatter(self):
        document = normalize_workflow_document(self._document())
        document["workflow"]["metadata"]["description"] = "检查接口: 避免 YAML 截断"

        markdown = render_skill_markdown(slug="interface-check", document=document)
        frontmatter = yaml.safe_load(markdown.split("---", 2)[1])

        self.assertEqual(frontmatter, {"name": "interface-check", "description": "检查接口: 避免 YAML 截断"})

    def test_validation_reports_domain_errors_without_rejecting_structure(self):
        document = normalize_workflow_document(self._document())
        document["workflow"]["nodes"][0]["isStart"] = False
        document["workflow"]["nodes"][0]["collectionCalls"][0]["inputBindings"] = {}

        codes = {item["code"] for item in validate_workflow_document(document)}

        self.assertIn("NO_START_STEP", codes)
        self.assertIn("MISSING_REQUIRED_BINDING", codes)

    def test_collection_name_and_command_are_required_for_sync_validation(self):
        document = normalize_workflow_document(self._document())
        definition = document["collectionSnapshots"][0]
        definition["metadata"]["name"] = ""
        definition["spec"]["commandTemplate"] = ""

        issues = validate_workflow_document(document)
        by_code = {item["code"]: item for item in issues}

        self.assertEqual(by_code["MISSING_COLLECTION_NAME"]["selection"]["field"], "metadata.name")
        self.assertEqual(by_code["MISSING_COLLECTION_COMMAND"]["selection"]["field"], "spec.commandTemplate")

    def test_parameter_names_and_multiline_commands_block_sync_validation(self):
        document = normalize_workflow_document(self._document())
        definition = document["collectionSnapshots"][0]
        definition["inputs"][0]["name"] = ""
        definition["spec"]["commandTemplate"] = "display interface\nverbose"

        codes = {item["code"] for item in validate_workflow_document(document)}

        self.assertIn("MISSING_PARAMETER_NAME", codes)
        self.assertIn("MULTILINE_COLLECTION_COMMAND", codes)

    def test_unscoped_call_outputs_conflicting_with_inputs_are_rejected(self):
        document = normalize_workflow_document(self._document())
        definition = document["collectionSnapshots"][0]
        definition["outputs"] = [{"id": "output-interface", "key": "interface_name", "name": "接口名称", "description": "", "dataType": "string"}]
        document["workflow"]["nodes"][0]["collectionCalls"][0]["key"] = ""

        self.assertIn("UNSCOPED_OUTPUT_CONFLICT", {item["code"] for item in validate_workflow_document(document)})

    def test_renderer_uses_collection_name_and_optional_call_namespace(self):
        document = normalize_workflow_document(self._document())
        definition = document["collectionSnapshots"][0]
        definition["outputs"] = [{"id": "output-version", "key": "version", "name": "版本", "description": "", "dataType": "string"}]
        call = document["workflow"]["nodes"][0]["collectionCalls"][0]
        call["name"] = ""
        call["key"] = ""

        direct = render_skill_markdown(slug="interface-check", document=document)
        self.assertIn("##### 接口状态", direct)
        self.assertIn("- `version` (string): 版本", direct)

        call["key"] = "status"
        scoped = render_skill_markdown(slug="interface-check", document=document)
        self.assertIn("- `status.version` (string): 版本", scoped)

    def test_document_schema_rejects_legacy_and_unknown_versions(self):
        with self.assertRaisesRegex(InvariantError, "schema version: 1"):
            migrate_workflow_document(1, self._document())
        with self.assertRaisesRegex(InvariantError, "schema version: 99"):
            migrate_workflow_document(99, self._document())

    def test_schema_rejects_removed_node_and_transition_keys(self):
        document = self._document()
        document["workflow"]["nodes"][0]["key"] = "legacy-step"

        with self.assertRaisesRegex(InvariantError, "Extra inputs are not permitted"):
            normalize_workflow_document(document)

    def test_schema_rejects_removed_transition_name_and_description(self):
        document = self._document()
        document["workflow"]["nodes"][0]["topology"][0]["name"] = "旧路径名称"

        with self.assertRaisesRegex(InvariantError, "Extra inputs are not permitted"):
            normalize_workflow_document(document)

    def test_duplicate_node_names_are_allowed_and_target_ids_are_validated(self):
        document = normalize_workflow_document(self._document())
        document["workflow"]["nodes"][1]["name"] = document["workflow"]["nodes"][0]["name"]

        self.assertEqual(validate_workflow_document(document), [])

        document["workflow"]["nodes"][0]["topology"][0]["target"]["id"] = "missing-node"
        self.assertIn("BROKEN_REFERENCE", {item["code"] for item in validate_workflow_document(document)})

    def test_duplicate_node_ids_are_rejected(self):
        document = normalize_workflow_document(self._document())
        document["workflow"]["nodes"][1]["id"] = document["workflow"]["nodes"][0]["id"]

        self.assertIn("DUPLICATE_NODE_ID", {item["code"] for item in validate_workflow_document(document)})

    def test_renderer_uses_unconditional_label_for_unnamed_path(self):
        document = normalize_workflow_document(self._document())
        transition = document["workflow"]["nodes"][0]["topology"][0]
        transition["name"] = ""
        transition["conditionText"] = ""
        transition["conditionExpression"] = ""

        markdown = render_skill_markdown(slug="interface-check", document=document)

        self.assertIn("- 无条件 -> 排查完成", markdown)

    def _document(self) -> dict:
        return {
            "documentType": "workflow_bundle",
            "workflow": {
                "id": "workflow-interface",
                "revision": 2,
                "metadata": {
                    "name": "接口状态排查",
                    "code": "IFACE",
                    "description": "检查接口状态。",
                    "industry": "网络",
                    "device": "交换机",
                    "versions": [],
                },
                "inputs": [
                    {
                        "id": "opaque-input-id",
                        "key": "interface_name",
                        "name": "接口名称",
                        "description": "待检查接口。",
                        "dataType": "string",
                        "required": True,
                    }
                ],
                "deviceRoles": [],
                "nodes": [
                    {
                        "id": "opaque-step-id",
                        "name": "采集接口",
                        "description": "读取接口状态。",
                        "isStart": True,
                        "inputs": [],
                        "collectionCalls": [
                            {
                                "id": "opaque-call-id",
                                "key": "interface_status",
                                "name": "接口状态",
                                "definition": {"id": "opaque-definition-id", "revision": 1},
                                "sampleCount": 1,
                                "inputBindings": {
                                    "opaque-parameter-id": {
                                        "kind": "workflow_input",
                                        "reference": {"input_id": "opaque-input-id"},
                                    }
                                },
                            }
                        ],
                        "topology": [
                            {
                                "id": "opaque-transition-id",
                                "target": {"id": "opaque-conclusion-id"},
                                "conditionText": "采集完成",
                                "conditionExpression": "status != ''",
                            }
                        ],
                        "stepType": "expression",
                    },
                    {
                        "id": "opaque-conclusion-id",
                        "name": "排查完成",
                        "rootCause": "接口异常。",
                        "repairRecommendation": "修复接口。",
                        "nodeType": "conclusion",
                    },
                ],
            },
            "collectionSnapshots": [
                {
                    "id": "opaque-definition-id",
                    "revision": 1,
                    "key": "interface_status",
                    "metadata": {
                        "name": "接口状态",
                        "description": "采集接口状态。",
                        "industry": "网络",
                        "device": "交换机",
                        "versions": [],
                        "tags": [],
                    },
                    "spec": {
                        "collectionType": "cli",
                        "commandTemplate": "display interface {{ interface_name }}",
                        "outputSamples": [
                            {
                                "id": "opaque-sample-id",
                                "name": "接口 Down 示例",
                                "stdout": "SECRET RAW OUTPUT",
                                "inputValues": {"interface_name": "SECRET INPUT VALUE"},
                            }
                        ],
                    },
                    "inputs": [
                        {
                            "id": "opaque-parameter-id",
                            "key": "interface_name",
                            "name": "接口名称",
                            "description": "待检查接口。",
                            "dataType": "string",
                            "required": True,
                        }
                    ],
                    "outputs": [],
                }
            ],
        }

    def _import_bundle(self) -> dict:
        return {
            "documentType": "workflow_import_bundle",
            "workflow": {
                "metadata": {"name": "接口检查", "code": "", "description": "检查接口状态。", "industry": "网络", "device": "交换机", "versions": []},
                "inputs": [{"id": "workflow-input-interface", "key": "interface_name", "name": "接口名称", "description": "", "dataType": "string", "required": True}],
                "deviceRoles": [],
                "nodes": [
                    {
                        "id": "step-start",
                        "name": "分析接口",
                        "description": "",
                        "isStart": True,
                        "inputs": [],
                        "collectionCalls": [
                            {
                                "id": "call-interface",
                                "key": "",
                                "name": "",
                                "definitionLocalId": "interface-status",
                                "sampleCount": 1,
                                "inputBindings": {
                                    "collection-input-interface": {
                                        "kind": "workflow_input",
                                        "reference": {"input_id": "workflow-input-interface"},
                                    }
                                },
                            }
                        ],
                        "topology": [],
                        "stepType": "expression",
                    }
                ],
            },
            "collections": [
                {
                    "localId": "interface-status",
                    "key": "interface_status",
                    "metadata": {"name": "接口状态", "description": "", "industry": "网络", "device": "交换机", "versions": [], "tags": []},
                    "spec": {"collectionType": "cli", "commandTemplate": "display interface {interface_name}", "outputSamples": []},
                    "inputs": [{"id": "collection-input-interface", "key": "interface_name", "name": "接口名称", "description": "", "dataType": "string", "required": True}],
                    "outputs": [],
                }
            ],
        }


if __name__ == "__main__":
    unittest.main()
