from __future__ import annotations

from pathlib import Path

from tests.test_worker_run_once import FakeLaminarClient, FakeOpencodeClient, FakeStore, _case_detail, _run_worker


def test_run_once_continues_when_laminar_datapoint_creation_fails(tmp_path: Path):
    store = FakeStore(_case_detail())
    laminar = FakeLaminarClient(create_error="Laminar unavailable")

    did_work = _run_worker(tmp_path, store=store, client=FakeOpencodeClient(), laminar=laminar)

    assert did_work is True
    assert laminar.update_count == 0
    assert store.failed is None
    assert store.retried is None
    assert store.finalized is not None
    assert store.finalized["runner_metadata"]["laminar_error"] == "Laminar unavailable"


def test_run_once_continues_when_laminar_datapoint_update_fails(tmp_path: Path):
    store = FakeStore(_case_detail())
    laminar = FakeLaminarClient(update_error="Laminar update failed")

    did_work = _run_worker(tmp_path, store=store, client=FakeOpencodeClient(), laminar=laminar)

    assert did_work is True
    assert laminar.update_count == 1
    assert store.failed is None
    assert store.retried is None
    assert store.finalized is not None
    assert store.finalized["runner_metadata"]["laminar_error"] == "Laminar update failed"
