from __future__ import annotations

import json
import re
import unittest
from copy import deepcopy
from pathlib import Path

import yaml

from skillhub.models.errors import InvariantError
from skillhub.models.rules.workflows import (
    materialize_workflow_import,
    migrate_workflow_document,
    normalize_workflow_document,
    normalize_workflow_import_bundle,
    render_skill_markdown,
    validate_workflow_document,
    validate_workflow_import_references,
)


class WorkflowRulesTest(unittest.TestCase):
    def test_device_role_key_and_schema_diagnostics(self):
        document = normalize_workflow_document(self._document())
        role = {"id": "role", "key": "bad-key", "name": "设备", "description": "", "required": True, "schema": {
            "type": "object", "title": "", "description": "", "properties": {"ip-address": {"type": "string", "title": "", "description": ""}}, "required": ["missing"], "additionalProperties": False,
        }}
        document["workflow"]["deviceRoles"] = [role]
        codes = {item["code"] for item in validate_workflow_document(document)}
        self.assertTrue({"INVALID_ROLE_KEY", "INVALID_DEVICE_ROLE_PROPERTY_KEY", "DEVICE_ROLE_SCHEMA_REQUIRED_INVALID"}.issubset(codes))

    def test_collection_binding_accepts_transitive_predecessor_output(self):
        document = self._document()
        workflow = document["workflow"]
        definition = document["collectionSnapshots"][0]
        definition["outputs"] = [{"id": "output-status", "key": "status", "required": True, "schema": {"type": "string", "title": "状态", "description": ""}}]
        first = workflow["nodes"][0]
        first["topology"] = [{"id": "path-next", "target": {"id": "step-next"}, "conditionText": "", "conditionExpression": ""}]
        second = {
            "id": "step-next",
            "name": "使用状态",
            "description": "",
            "isStart": False,
            "collectionCalls": [{
                "id": "call-next",
                "key": "next",
                "name": "后续采集",
                "definition": {"id": definition["id"], "revision": 1},
                "sampleCount": 1,
                "inputBindings": {"opaque-parameter-id": {"kind": "collection_output", "reference": {"call_id": "opaque-call-id", "output_id": "output-status"}}},
            }],
            "topology": [{"id": "path-done", "target": {"id": "opaque-conclusion-id"}, "conditionText": "", "conditionExpression": ""}],
            "stepType": "expression",
        }
        workflow["nodes"].insert(1, second)

        self.assertNotIn("BROKEN_REFERENCE", {item["code"] for item in validate_workflow_document(normalize_workflow_document(document))})

    def test_collection_binding_rejects_same_step_later_call(self):
        document = normalize_workflow_document(self._document())
        step = document["workflow"]["nodes"][0]
        call = deepcopy(step["collectionCalls"][0])
        call["id"] = "later-call"
        call["inputBindings"] = {"opaque-parameter-id": {"kind": "collection_output", "reference": {"call_id": "later-call", "output_id": "missing"}}}
        step["collectionCalls"].append(call)

        self.assertIn("FORWARD_OUTPUT_BINDING", {item["code"] for item in validate_workflow_document(document)})

    def test_condition_text_template_uses_step_expression_scope(self):
        document = normalize_workflow_document(self._document())
        document["collectionSnapshots"][0]["outputs"] = [{
            "id": "output-status",
            "key": "status",
            "required": True,
            "schema": {"type": "string", "title": "状态", "description": ""},
        }]
        transition = document["workflow"]["nodes"][0]["topology"][0]
        transition["conditionText"] = "状态：{{ outputs.interface_status.status }}"
        self.assertNotIn("UNKNOWN_PROPERTY", {item["code"] for item in validate_workflow_document(document)})

        transition["conditionText"] = "状态：{{ outputs.missing.status }}"
        issues = validate_workflow_document(document)
        self.assertIn("UNKNOWN_PROPERTY", {item["code"] for item in issues})
        self.assertTrue(any(item["selection"].get("field") == "conditionText" for item in issues if item["code"] == "UNKNOWN_PROPERTY"))

    def test_device_role_schema_is_available_to_condition_and_conclusion_templates(self):
        document = normalize_workflow_document(self._document())
        document["workflow"]["deviceRoles"] = [{
            "id": "role-primary", "key": "primary", "name": "主设备", "description": "", "required": True,
            "schema": {
                "type": "object", "title": "主设备参数", "description": "", "additionalProperties": False, "required": ["connection"],
                "properties": {"connection": {"type": "object", "title": "连接", "description": "", "additionalProperties": False, "required": ["ip"], "properties": {"ip": {"type": "string", "title": "IP", "description": ""}}}},
            },
        }]
        document["workflow"]["nodes"][0]["topology"][0]["conditionText"] = "目标：{{ topo.devices.primary.connection.ip }}"
        document["workflow"]["nodes"][1]["rootCause"] = "设备地址：{{ topo.devices.primary.connection.ip }}"

        issues = validate_workflow_document(document)

        self.assertNotIn("UNKNOWN_PROPERTY", {item["code"] for item in issues})

        bundle = self._import_bundle()
        bundle["workflow"]["deviceRoles"] = deepcopy(document["workflow"]["deviceRoles"])
        bundle["workflow"]["nodes"][0]["topology"] = [{
            "id": "path-role", "target": {"id": "step-start"}, "conditionText": "目标：{{ topo.devices.primary.connection.ip }}", "conditionExpression": "",
        }]
        validate_workflow_import_references(normalize_workflow_import_bundle(bundle))

    def test_collection_binding_accepts_device_role_object_field_and_rejects_array_path(self):
        document = normalize_workflow_document(self._document())
        document["workflow"]["deviceRoles"] = [{
            "id": "role-primary", "key": "primary", "name": "主设备", "description": "", "required": True,
            "schema": {
                "type": "object", "title": "参数", "description": "", "additionalProperties": False, "required": ["connection", "interfaces"],
                "properties": {
                    "connection": {"type": "object", "title": "连接", "description": "", "additionalProperties": False, "required": ["ip"], "properties": {"ip": {"type": "string", "title": "IP", "description": ""}}},
                    "interfaces": {"type": "array", "title": "接口", "description": "", "items": {"type": "string", "title": "接口", "description": ""}},
                },
            },
        }]
        call = document["workflow"]["nodes"][0]["collectionCalls"][0]
        call["inputBindings"] = {"opaque-parameter-id": {"kind": "device_role_field", "reference": {"role_id": "role-primary", "path": "connection.ip"}}}
        self.assertNotIn("INVALID_DEVICE_ROLE_BINDING_PATH", {item["code"] for item in validate_workflow_document(document)})
        call["inputBindings"]["opaque-parameter-id"]["reference"]["path"] = "interfaces"
        self.assertIn("INVALID_DEVICE_ROLE_BINDING_PATH", {item["code"] for item in validate_workflow_document(document)})

    def test_import_binding_accepts_predecessor_step_output(self):
        bundle = self._import_bundle()
        definition = bundle["collections"][0]
        definition["outputs"] = [{"id": "output-status", "key": "status", "required": True, "schema": {"type": "string", "title": "状态", "description": ""}}]
        first = bundle["workflow"]["nodes"][0]
        first["topology"] = [{"id": "path-next", "target": {"id": "step-next"}, "conditionText": "", "conditionExpression": ""}]
        bundle["workflow"]["nodes"].append({
            "id": "step-next", "name": "使用状态", "description": "", "isStart": False,
            "collectionCalls": [{
                "id": "call-next", "key": "", "name": "", "definitionLocalId": "interface-status", "sampleCount": 1,
                "inputBindings": {"collection-input-interface": {"kind": "collection_output", "reference": {"call_id": "call-interface", "output_id": "output-status"}}},
            }],
            "topology": [], "stepType": "expression",
        })

        validate_workflow_import_references(normalize_workflow_import_bundle(bundle))

    def test_import_rejects_invalid_condition_text_template(self):
        bundle = self._import_bundle()
        bundle["workflow"]["nodes"][0]["topology"] = [{
            "id": "path-loop",
            "target": {"id": "step-start"},
            "conditionText": "状态：{{ outputs.missing.status }}",
            "conditionExpression": "",
        }]
        with self.assertRaisesRegex(InvariantError, "condition template"):
            validate_workflow_import_references(normalize_workflow_import_bundle(bundle))

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

    def test_import_device_role_binding_resolves_object_field_and_rejects_array_path(self):
        bundle = self._import_bundle()
        bundle["workflow"]["deviceRoles"] = [{
            "id": "role-primary",
            "key": "primary",
            "name": "主设备",
            "description": "",
            "required": True,
            "schema": {
                "type": "object",
                "title": "参数",
                "description": "",
                "properties": {
                    "connection": {
                        "type": "object",
                        "title": "连接",
                        "description": "",
                        "properties": {"ip": {"type": "string", "title": "IP", "description": ""}},
                        "required": ["ip"],
                        "additionalProperties": False,
                    },
                    "interfaces": {
                        "type": "array",
                        "title": "接口",
                        "description": "",
                        "items": {"type": "string", "title": "接口", "description": ""},
                    },
                },
                "required": ["connection", "interfaces"],
                "additionalProperties": False,
            },
        }]
        call = bundle["workflow"]["nodes"][0]["collectionCalls"][0]
        call["inputBindings"]["collection-input-interface"] = {
            "kind": "device_role_field",
            "reference": {"role_id": "role-primary", "path": "connection.ip"},
        }
        validate_workflow_import_references(normalize_workflow_import_bundle(bundle))

        call["inputBindings"]["collection-input-interface"]["reference"]["path"] = "interfaces"
        with self.assertRaisesRegex(InvariantError, "device role binding path"):
            validate_workflow_import_references(normalize_workflow_import_bundle(bundle))

    def test_import_bundle_materializes_target_identity_and_collection_references(self):
        source = self._import_bundle()
        source["workflow"]["metadata"]["symptom"] = "接口频繁闪断。"
        bundle = normalize_workflow_import_bundle(source)

        document = materialize_workflow_import(
            bundle,
            workflow_id="workflow-target",
            revision=7,
            collection_mappings={"interface-status": ("collection-generated", 1)},
        )

        self.assertEqual(document["workflow"]["id"], "workflow-target")
        self.assertEqual(document["workflow"]["revision"], 7)
        self.assertEqual(document["workflow"]["metadata"]["symptom"], "接口频繁闪断。")
        self.assertEqual(
            document["workflow"]["nodes"][0]["collectionCalls"][0]["definition"],
            {"id": "collection-generated", "revision": 1},
        )
        self.assertNotIn("definitionLocalId", document["workflow"]["nodes"][0]["collectionCalls"][0])

    def test_renderer_is_deterministic_and_uses_readable_binding_references(self):
        document = normalize_workflow_document(self._document())
        document["workflow"]["metadata"]["symptom"] = "不应写入 Skill 的问题现象。"

        first = render_skill_markdown(slug="interface-check", document=document)
        second = render_skill_markdown(slug="interface-check", document=document)

        self.assertEqual(first, second)
        self.assertIn("全局输入 `interface_name` (接口名称)", first)
        self.assertNotIn("opaque-input-id", first)
        self.assertNotIn("opaque-parameter-id", first)
        self.assertNotIn("SECRET RAW OUTPUT", first)
        self.assertNotIn("SECRET INPUT VALUE", first)
        self.assertNotIn("不应写入 Skill 的问题现象", first)
        self.assertNotIn("- Key:", first)
        self.assertIn("接口 Down 示例", first)
        self.assertIn("- 设备角色: 单设备", first)
        self.assertIn("- 采集次数: 1", first)

    def test_v3_metadata_defaults_missing_symptom(self):
        document = normalize_workflow_document(self._document())

        self.assertEqual(document["workflow"]["metadata"]["symptom"], "")
        self.assertEqual(migrate_workflow_document(3, self._document())["workflow"]["metadata"]["symptom"], "")

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
        definition["inputs"][0]["schema"]["title"] = ""
        definition["spec"]["commandTemplate"] = "display interface\nverbose"

        codes = {item["code"] for item in validate_workflow_document(document)}

        self.assertIn("MISSING_PARAMETER_NAME", codes)
        self.assertIn("MULTILINE_COLLECTION_COMMAND", codes)

    def test_unscoped_call_outputs_conflicting_with_inputs_are_rejected(self):
        document = normalize_workflow_document(self._document())
        definition = document["collectionSnapshots"][0]
        definition["outputs"] = [
            {"id": "output-interface", "key": "interface_name", "required": True, "schema": {"type": "string", "title": "接口名称", "description": ""}}
        ]
        document["workflow"]["nodes"][0]["collectionCalls"][0]["key"] = ""

        self.assertIn("UNSCOPED_OUTPUT_CONFLICT", {item["code"] for item in validate_workflow_document(document)})

    def test_unscoped_output_conflicts_across_predecessor_steps_are_rejected(self):
        document = normalize_workflow_document(self._document())
        definition = document["collectionSnapshots"][0]
        definition["outputs"] = [
            {
                "id": "output-state",
                "key": "state",
                "required": True,
                "schema": {"type": "string", "title": "状态", "description": ""},
            },
            {
                "id": "output-invalid",
                "key": "router-status",
                "required": True,
                "schema": {"type": "string", "title": "非法字段", "description": ""},
            },
        ]
        first = document["workflow"]["nodes"][0]
        first["collectionCalls"][0]["key"] = ""
        second = deepcopy(first)
        second["id"] = "second-step"
        second["name"] = "再次采集"
        second["isStart"] = False
        second["collectionCalls"][0]["id"] = "second-call"
        second["topology"][0]["id"] = "second-transition"
        first["topology"][0]["target"] = {"id": second["id"]}
        document["workflow"]["nodes"].insert(1, second)

        conflicts = [
            item
            for item in validate_workflow_document(document)
            if item["code"] == "UNSCOPED_OUTPUT_CONFLICT"
        ]

        self.assertEqual(
            {item["selection"]["itemId"] for item in conflicts},
            {"opaque-call-id", "second-call"},
        )
        self.assertEqual(len(conflicts), 2)

    def test_renderer_uses_collection_name_and_optional_call_namespace(self):
        document = normalize_workflow_document(self._document())
        definition = document["collectionSnapshots"][0]
        definition["outputs"] = [{"id": "output-version", "key": "version", "required": True, "schema": {"type": "string", "title": "版本", "description": ""}}]
        call = document["workflow"]["nodes"][0]["collectionCalls"][0]
        call["name"] = ""
        call["key"] = ""

        direct = render_skill_markdown(slug="interface-check", document=document)
        self.assertIn("##### 接口状态", direct)
        self.assertIn("- `version` (string, 必填): 版本", direct)

        call["key"] = "status"
        scoped = render_skill_markdown(slug="interface-check", document=document)
        self.assertIn("- `outputs.status.version` (string, 必填): 版本", scoped)

    def test_document_schema_rejects_legacy_and_unknown_versions(self):
        with self.assertRaisesRegex(InvariantError, "schema version: 1"):
            migrate_workflow_document(1, self._document())
        with self.assertRaisesRegex(InvariantError, "schema version: 2"):
            migrate_workflow_document(2, self._document())
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

    def test_schema_rejects_v2_step_inputs_output_names_and_bindings(self):
        document = self._document()
        document["workflow"]["nodes"][0]["inputs"] = []
        with self.assertRaisesRegex(InvariantError, "Extra inputs are not permitted"):
            normalize_workflow_document(document)

        document = self._document()
        document["collectionSnapshots"][0]["outputs"] = [
            {"id": "output-status", "key": "status", "required": True, "schema": {"type": "string", "title": "状态", "description": ""}, "name": "状态"}
        ]
        with self.assertRaisesRegex(InvariantError, "Extra inputs are not permitted"):
            normalize_workflow_document(document)

        document = self._document()
        document["workflow"]["nodes"][0]["collectionCalls"][0]["inputBindings"]["opaque-parameter-id"] = {
            "kind": "step_input",
            "reference": {"input_id": "legacy-step-input"},
        }
        with self.assertRaisesRegex(InvariantError, "workflow_input"):
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
        transition["conditionText"] = ""
        transition["conditionExpression"] = ""

        markdown = render_skill_markdown(slug="interface-check", document=document)

        self.assertIn("- 无条件 -> 排查完成", markdown)

    def test_call_keys_are_step_scoped_and_multi_sample_keys_are_identifiers(self):
        document = normalize_workflow_document(self._document())
        first_step = document["workflow"]["nodes"][0]
        duplicate_step = deepcopy(first_step)
        duplicate_step["id"] = "second-step"
        duplicate_step["isStart"] = False
        duplicate_step["collectionCalls"][0]["id"] = "second-call"
        duplicate_step["topology"] = []
        document["workflow"]["nodes"].insert(1, duplicate_step)

        self.assertNotIn("DUPLICATE_CALL_KEY", {item["code"] for item in validate_workflow_document(document)})

        duplicate_call = deepcopy(first_step["collectionCalls"][0])
        duplicate_call["id"] = "same-step-call"
        first_step["collectionCalls"].append(duplicate_call)
        self.assertIn("DUPLICATE_CALL_KEY", {item["code"] for item in validate_workflow_document(document)})
        first_step["collectionCalls"].pop()

        document["workflow"]["nodes"].pop(1)
        call = first_step["collectionCalls"][0]
        call["sampleCount"] = 2
        call["key"] = ""
        self.assertIn("MULTI_SAMPLE_CALL_KEY_REQUIRED", {item["code"] for item in validate_workflow_document(document)})
        call["key"] = "not-valid"
        self.assertIn("INVALID_MULTI_SAMPLE_CALL_KEY", {item["code"] for item in validate_workflow_document(document)})

    def test_workflow_validation_aggregates_multi_sample_index_warnings(self):
        document = normalize_workflow_document(self._document())
        call = document["workflow"]["nodes"][0]["collectionCalls"][0]
        call["sampleCount"] = 2
        document["collectionSnapshots"][0]["outputs"] = [
            {
                "id": "output-status",
                "key": "status",
                "required": True,
                "schema": {"type": "string", "title": "状态", "description": ""},
            }
        ]
        transition = document["workflow"]["nodes"][0]["topology"][0]
        transition["conditionExpression"] = "outputs.interface_status.status == 'up'"

        warnings = [item for item in validate_workflow_document(document) if item["code"] == "SAMPLE_INDEX_REQUIRED"]

        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0]["severity"], "warning")
        self.assertEqual(warnings[0]["selection"]["itemId"], "opaque-transition-id")

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
                "inputs": [
                    {"id": "workflow-input-interface", "key": "interface_name", "name": "接口名称", "description": "", "dataType": "string", "required": True}
                ],
                "deviceRoles": [],
                "nodes": [
                    {
                        "id": "step-start",
                        "name": "分析接口",
                        "description": "",
                        "isStart": True,
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
                    "inputs": [
                        {
                            "id": "collection-input-interface",
                            "key": "interface_name",
                            "name": "接口名称",
                            "description": "",
                            "dataType": "string",
                            "required": True,
                        }
                    ],
                    "outputs": [],
                }
            ],
        }


if __name__ == "__main__":
    unittest.main()
