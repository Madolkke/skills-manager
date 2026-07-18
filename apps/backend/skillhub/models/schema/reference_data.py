from __future__ import annotations

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from skillhub.models.schema.reviews import PublishTarget

DEFAULT_PUBLISH_GATE = {
    "type": "group",
    "op": "and",
    "children": [
        {"type": "check", "check_id": "min_responses", "params": {"min": 1}},
        {"type": "check", "check_id": "no_negative_score", "params": {}},
    ],
}

PUBLISH_TARGET_ROWS = (
    ("target_yunxi", "yunxi", "云析", "云析发布源"),
    ("target_agentcenter", "agentcenter", "AgentCenter", "AgentCenter 发布源"),
    ("target_custom1", "custom1", "自定义1", "预留自定义发布源 1"),
    ("target_custom2", "custom2", "自定义2", "预留自定义发布源 2"),
)


def seed_reference_data(session: Session) -> None:
    statement = insert(PublishTarget).values(
        [
            {
                "id": target_id,
                "target_key": key,
                "name": name,
                "description": description,
                "enabled": True,
                "auto_publish_enabled": False,
                "gate_expression": DEFAULT_PUBLISH_GATE,
                "config": {},
                "created_by": "system",
            }
            for target_id, key, name, description in PUBLISH_TARGET_ROWS
        ]
    )
    session.execute(statement.on_conflict_do_nothing(index_elements=[PublishTarget.target_key]))
