from __future__ import annotations

from typing import Any


DEFAULT_GATE_EXPRESSION = {
    "type": "group",
    "op": "and",
    "children": [
        {"type": "check", "check_id": "min_responses", "params": {"min": 1}},
        {"type": "check", "check_id": "no_negative_score", "params": {}},
    ],
}

FIXED_PUBLISH_TARGETS = [
    {"id": "target_yunxi", "target_key": "yunxi", "name": "云析", "description": "云析发布源"},
    {"id": "target_agentcenter", "target_key": "agentcenter", "name": "AgentCenter", "description": "AgentCenter 发布源"},
    {"id": "target_custom1", "target_key": "custom1", "name": "自定义1", "description": "预留自定义发布源 1"},
    {"id": "target_custom2", "target_key": "custom2", "name": "自定义2", "description": "预留自定义发布源 2"},
]

FIXED_PUBLISH_TARGET_KEYS = {item["target_key"] for item in FIXED_PUBLISH_TARGETS}

REVIEW_CHECK_DEFINITIONS: dict[str, dict[str, Any]] = {
    "no_negative_score": {
        "id": "no_negative_score",
        "label": "没有 -1 分",
        "description": "没有评审人给出 -1 分。",
        "params_schema": [],
    },
    "no_neutral_score": {
        "id": "no_neutral_score",
        "label": "没有 0 分",
        "description": "没有评审人给出 0 分。",
        "params_schema": [],
    },
    "all_reviewers_responded": {
        "id": "all_reviewers_responded",
        "label": "全部评审人已回复",
        "description": "发起评审时快照的所有评审人均已提交评分。",
        "params_schema": [],
    },
    "min_responses": {
        "id": "min_responses",
        "label": "最低回复人数",
        "description": "已提交评分的评审人数至少达到指定数量。",
        "params_schema": [{"name": "min", "label": "最低人数", "type": "number", "min": 1, "default": 1}],
    },
    "total_score_at_least": {
        "id": "total_score_at_least",
        "label": "总分至少为",
        "description": "所有已回复评审分数求和至少达到指定值。",
        "params_schema": [{"name": "min", "label": "最低总分", "type": "number", "default": 1}],
    },
    "average_score_at_least": {
        "id": "average_score_at_least",
        "label": "平均分至少为",
        "description": "已回复评审的平均分至少达到指定值，范围通常为 -1 到 1。",
        "params_schema": [{"name": "min", "label": "最低平均分", "type": "number", "step": 0.1, "default": 0.5}],
    },
    "positive_ratio_at_least": {
        "id": "positive_ratio_at_least",
        "label": "正分率至少为",
        "description": "1 分人数占已回复人数比例至少达到指定百分比。",
        "params_schema": [{"name": "min", "label": "最低正分率 (%)", "type": "number", "min": 0, "max": 100, "default": 50}],
    },
    "negative_count_at_most": {
        "id": "negative_count_at_most",
        "label": "负分数至多为",
        "description": "-1 分人数不超过指定数量。",
        "params_schema": [{"name": "max", "label": "最多负分人数", "type": "number", "min": 0, "default": 0}],
    },
}

REVIEW_CHECK_LABELS = {key: value["label"] for key, value in REVIEW_CHECK_DEFINITIONS.items()}


def publish_gate_check_definitions() -> list[dict[str, Any]]:
    return [REVIEW_CHECK_DEFINITIONS[key] for key in REVIEW_CHECK_DEFINITIONS]
