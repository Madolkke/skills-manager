from __future__ import annotations

import base64


def encode_skill_tag_resource_id(group_id: str, value: str) -> str:
    clean_group_id = group_id.strip()
    clean_value = value.strip()
    encoded_value = base64.urlsafe_b64encode(clean_value.encode("utf-8")).decode("ascii").rstrip("=")
    return f"{clean_group_id}:{encoded_value}"


def decode_skill_tag_resource_id(resource_id: str) -> tuple[str, str]:
    group_id, encoded_value = resource_id.split(":", 1)
    padding = "=" * (-len(encoded_value) % 4)
    value = base64.urlsafe_b64decode(f"{encoded_value}{padding}".encode("ascii")).decode("utf-8")
    return group_id, value
