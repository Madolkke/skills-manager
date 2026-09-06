from unittest.mock import Mock

import pytest

from skillhub.services.command_library import CommandLibraryService
from skillhub.views.request_models.command_library import SystemCommandUpdatePayload


def _store():
    """保留旧命令内容以验证局部更新。"""
    store = Mock()
    store.get_system_command.return_value = {
        "key": "status", "name": "状态", "metadata": {"name": "状态"},
        "samples": [{"name": "正常", "command": "show status", "stdout": "ok"}],
        "outputSchema": {"type": "object", "properties": {}, "required": []},
        "ttp": "parser",
    }
    return store


@pytest.mark.parametrize("payload", [{"enabled": False}, {"samples": None, "outputSchema": None, "ttp": None}])
def test_partial_update_preserves_omitted_and_null_document_fields(payload):
    store = _store()
    CommandLibraryService(store).update_system(
        command_id="status", actor="admin",
        payload=SystemCommandUpdatePayload(**payload).model_dump(by_alias=True),
    )
    document = store.update_system_command.call_args.kwargs["document"]
    for field in ("samples", "outputSchema", "ttp"):
        assert document[field] == store.get_system_command.return_value[field]


def test_partial_update_clears_explicit_empty_values():
    store = _store()
    CommandLibraryService(store).update_system(
        command_id="status", actor="admin",
        payload=SystemCommandUpdatePayload(samples=[], ttp="").model_dump(by_alias=True),
    )
    document = store.update_system_command.call_args.kwargs["document"]
    assert document["samples"] == []
    assert document["ttp"] == ""
