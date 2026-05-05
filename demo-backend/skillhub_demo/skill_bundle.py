from __future__ import annotations

import json
from typing import Dict


def normalize_bundle_files(files: Dict[str, str]) -> Dict[str, str]:
    if not files:
        raise ValueError("Skill bundle files cannot be empty")
    normalized: Dict[str, str] = {}
    for raw_path, content in files.items():
        if not isinstance(raw_path, str) or not isinstance(content, str):
            raise ValueError("Skill bundle files must map string paths to string content")
        path = raw_path.strip().lstrip("./")
        parts = [part for part in path.split("/") if part]
        if not parts or any(part == ".." for part in parts):
            raise ValueError("Invalid skill bundle path: %s" % raw_path)
        normalized["/".join(parts)] = content
    return dict(sorted(normalized.items()))


def skill_md_metadata(content: str) -> Dict[str, str]:
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("SKILL.md must start with YAML frontmatter")

    end_index = None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_index = index
            break
    if end_index is None:
        raise ValueError("SKILL.md frontmatter must end with ---")

    fields: Dict[str, str] = {}
    for line in lines[1:end_index]:
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        fields[key.strip()] = value.strip().strip('"').strip("'")

    skill_name = fields.get("name", "")
    description = fields.get("description", "")
    if not skill_name or not description:
        raise ValueError("SKILL.md frontmatter must include name and description")
    if not all(char.islower() or char.isdigit() or char == "-" for char in skill_name):
        raise ValueError("SKILL.md name must use lowercase letters, digits, and hyphens")
    return {"name": skill_name, "description": description}


def skill_bundle_payload(name: str, files: Dict[str, str]) -> Dict[str, object]:
    normalized_files = normalize_bundle_files(files)
    skill_md = normalized_files.get("SKILL.md")
    if skill_md is None:
        raise ValueError("Skill bundle must include SKILL.md")
    metadata = skill_md_metadata(skill_md)
    return {
        "name": name.strip() or metadata["name"],
        "metadata": metadata,
        "files": normalized_files,
    }


def skill_bundle_content(name: str, files: Dict[str, str]) -> str:
    return json.dumps(skill_bundle_payload(name, files), ensure_ascii=False, sort_keys=True)
