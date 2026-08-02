from __future__ import annotations

from typing import Any


def executor_workflow_document(*, suffix: str = "") -> dict[str, Any]:
    definition_environment = f"collection-environment{suffix}"
    definition_check = f"collection-check{suffix}"
    return {
        "documentType": "workflow_bundle",
        "workflow": {
            "id": f"workflow-executor{suffix}",
            "revision": 4,
            "metadata": {"name": "PTN故障快排", "description": "执行器转换测试。"},
            "inputs": [
                _parameter("input-slot", "slot-id", "string", "要检查的槽位号"),
                _parameter("input-limit", "limit", "integer", "重试次数"),
                _parameter("input-ratio", "ratio", "number", "阈值"),
                _parameter("input-enabled", "enabled", "boolean", "是否启用"),
            ],
            "deviceRoles": [],
            "nodes": [
                {
                    "id": "step-prepare",
                    "name": "准备环境",
                    "description": "执行准备命令。",
                    "isStart": True,
                    "collectionCalls": [
                        {
                            "id": "call-environment",
                            "key": "",
                            "name": "准备环境",
                            "definition": {"id": definition_environment, "revision": 1},
                            "sampleCount": 1,
                            "inputBindings": {
                                "parameter-slot": {"kind": "workflow_input", "reference": {"input_id": "input-slot"}},
                                "parameter-threshold": {"kind": "literal", "reference": {}, "value": 0.8},
                                "parameter-enabled": {"kind": "literal", "reference": {}, "value": False},
                                "parameter-note": {"kind": "literal", "reference": {}, "value": None},
                            },
                        },
                        {
                            "id": "call-check",
                            "key": "memory.stats",
                            "name": "检查内存",
                            "definition": {"id": definition_check, "revision": 1},
                            "sampleCount": 1,
                            "inputBindings": {
                                "parameter-memory": {
                                    "kind": "collection_output",
                                    "reference": {"call_id": "call-environment", "output_id": "output-memory"},
                                }
                            },
                        },
                    ],
                    "topology": [
                        {
                            "id": "transition-next",
                            "target": {"id": "step-confirm"},
                            "conditionText": "需要复核",
                            "conditionExpression": "outputs.memory-percentage > 0.8",
                        },
                        {
                            "id": "transition-done",
                            "target": {"id": "conclusion-normal"},
                            "conditionText": "检查完成",
                            "conditionExpression": "",
                        },
                    ],
                    "stepType": "expression",
                },
                {
                    "id": "step-confirm",
                    "name": "确认状态",
                    "description": "确认设备状态。",
                    "isStart": True,
                    "collectionCalls": [],
                    "topology": [
                        {
                            "id": "transition-confirmed",
                            "target": {"id": "conclusion-normal"},
                            "conditionText": "确认完成",
                            "conditionExpression": "true",
                        }
                    ],
                    "stepType": "expression",
                },
                {
                    "id": "conclusion-normal",
                    "name": "无异常",
                    "rootCause": "忽略的根因",
                    "repairRecommendation": "忽略的建议",
                    "nodeType": "conclusion",
                },
            ],
        },
        "collectionSnapshots": [
            {
                "id": definition_environment,
                "revision": 1,
                "key": "environment",
                "metadata": {"name": "准备环境"},
                "spec": {
                    "collectionType": "cli",
                    "commandTemplate": "screen-length 0 temporary",
                    "outputSamples": [{"id": "sample-ignored", "name": "忽略", "stdout": "ignored", "inputValues": {}}],
                },
                "inputs": [
                    _parameter("parameter-slot", "slot-id", "string", "要检查的槽位号"),
                    _parameter("parameter-threshold", "threshold", "number", "内存阈值"),
                    _parameter("parameter-enabled", "enabled", "boolean", "是否启用"),
                    _parameter("parameter-note", "note", "string", "备注"),
                    _parameter("parameter-unbound", "unbound", "integer", "未绑定参数"),
                ],
                "outputs": [_output("output-memory", "memory-percentage", "number", "内存使用率")],
            },
            {
                "id": definition_check,
                "revision": 1,
                "key": "check",
                "metadata": {"name": "检查内存"},
                "spec": {"collectionType": "cli", "commandTemplate": "display memory", "outputSamples": []},
                "inputs": [_parameter("parameter-memory", "memory", "number", "内存使用率")],
                "outputs": [_output("output-ok", "ok-flag", "boolean", "是否正常")],
            },
        ],
    }


def _parameter(identifier: str, key: str, value_type: str, description: str) -> dict[str, Any]:
    return {
        "id": identifier,
        "key": key,
        "required": True,
        "schema": {"type": value_type, "title": key, "description": description},
    }


def _output(identifier: str, key: str, value_type: str, description: str) -> dict[str, Any]:
    return {
        "id": identifier,
        "key": key,
        "required": True,
        "schema": {"type": value_type, "title": key, "description": description},
    }
