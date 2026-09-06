from copy import deepcopy
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from skillhub.models.errors import InvariantError
from skillhub.models.operations.command_library import CommandLibraryStoreMixin, _source_to_collection


def _fixture():
    """两个调用共享同一个来源，后一个读取前一个输出。"""
    source = SimpleNamespace(
        key="show", name="新名称", description="", expression="show <name>",
        captures={"name": {}}, metadata_json={},
        document={"outputSchema": {"type": "object", "properties": {"status": {"type": "string"}}, "required": []}},
    )
    current = _source_to_collection(source, definition_id="col", revision=1, source_id="sys")
    current["metadata"]["name"] = "旧名称"
    first = {"id": "a", "key": "first", "definition": {"id": "col", "revision": 1},
             "inputBindings": {"input_name": {"kind": "literal", "value": "eth0"}}}
    second = {"id": "b", "key": "second", "definition": {"id": "col", "revision": 1},
              "inputBindings": {"input_name": {"kind": "collection_output", "reference": {"call_id": "a", "output_id": "output_status"}}}}
    document = {"collectionSnapshots": [current], "workflow": {"inputs": [], "nodes": [
        {"id": "step", "collectionCalls": [first, second], "topology": []},
    ]}}
    connection = Mock()
    row = Mock()
    row.mappings.return_value.one_or_none.return_value = {"source_system_command_id": "sys", "latest_revision": 1}
    result = Mock()
    result.scalar_one_or_none.return_value = source
    connection.execute.side_effect = [row, result, Mock(), Mock()]
    store = Mock()
    store._document_digest.return_value = "digest"
    return store, connection, document, source


def test_repeated_source_binding_uses_candidate_snapshot_and_writes_once():
    store, connection, document, _ = _fixture()
    mappings = CommandLibraryStoreMixin.sync_system_sources(
        store, connection, document=document, actor="tester", created_at=datetime.now(timezone.utc),
    )
    assert mappings == {("col", 1): ("col", 2)}
    assert [c["definition"]["revision"] for c in document["workflow"]["nodes"][0]["collectionCalls"]] == [2, 2]
    assert connection.execute.call_count == 4


def test_incompatible_source_does_not_write_or_rewrite_document():
    store, connection, document, source = _fixture()
    source.document["outputSchema"]["properties"] = {"state": {"type": "string"}}
    original = deepcopy(document)
    with pytest.raises(InvariantError):
        CommandLibraryStoreMixin.sync_system_sources(
            store, connection, document=document, actor="tester", created_at=datetime.now(timezone.utc),
        )
    assert document == original
    assert connection.execute.call_count == 2


def test_existing_missing_literal_draft_does_not_block_metadata_refresh():
    store, connection, document, _ = _fixture()
    document["workflow"]["nodes"][0]["collectionCalls"][0]["inputBindings"]["input_name"]["value"] = ""
    mappings = CommandLibraryStoreMixin.sync_system_sources(
        store, connection, document=document, actor="tester", created_at=datetime.now(timezone.utc),
    )
    assert mappings == {("col", 1): ("col", 2)}
