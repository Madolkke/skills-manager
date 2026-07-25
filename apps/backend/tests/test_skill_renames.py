from __future__ import annotations

import base64
import json

import pytest

from skillhub.models.errors import InvariantError
from skillhub.models.rules.skill_imports import parse_skill_import_source
from skillhub.models.rules.skill_renames import rename_skill_bundle


def test_rename_skill_bundle_updates_only_skill_identity() -> None:
    binary = b"\x00\x01skillhub"
    source = {
        "kind": "files",
        "files": [
            {
                "path": "SKILL.md",
                "content_text": "---\n# 保留这条注释\nname: old-skill\ndescription: '中文说明'\n---\n# Body\nKeep this.\n",
            },
            {"path": "references/checklist.md", "content_text": "Check everything.\n"},
            {"path": "assets/data.bin", "content_base64": base64.b64encode(binary).decode("ascii")},
        ],
    }
    original = parse_skill_import_source(source)

    renamed = rename_skill_bundle(original.manifest_text, new_slug="new-skill")
    manifest = json.loads(renamed.manifest_text)
    files = {item["path"]: item for item in manifest["files"]}

    assert manifest["metadata"] == {"name": "new-skill", "description": "中文说明"}
    assert files["SKILL.md"]["content_text"] == "---\n# 保留这条注释\nname: new-skill\ndescription: '中文说明'\n---\n# Body\nKeep this.\n"
    assert "# Body\nKeep this." in files["SKILL.md"]["content_text"]
    assert files["references/checklist.md"]["content_text"] == "Check everything.\n"
    assert base64.b64decode(files["assets/data.bin"]["content_base64"]) == binary
    assert renamed.file_count == 3
    assert renamed.digest != original.digest
    assert "old-skill" in original.manifest_text


def test_rename_skill_bundle_rejects_corrupt_file_digest() -> None:
    original = parse_skill_import_source(
        {
            "kind": "files",
            "files": [
                {
                    "path": "SKILL.md",
                    "content_text": "---\nname: old-skill\ndescription: Test\n---\n",
                }
            ],
        }
    )
    manifest = json.loads(original.manifest_text)
    manifest["files"][0]["sha256"] = "corrupt"

    with pytest.raises(InvariantError, match="digest"):
        rename_skill_bundle(json.dumps(manifest), new_slug="new-skill")
