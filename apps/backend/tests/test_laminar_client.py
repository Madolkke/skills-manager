from __future__ import annotations

from uuid import UUID, uuid4

from skillhub_worker import laminar_client


class FakeEvals:
    def __init__(self):
        self.evaluation_id = uuid4()
        self.datapoint_id = uuid4()
        self.created = None
        self.updated = None

    def create_evaluation(self, *, name, metadata):
        self.created = {"name": name, "metadata": metadata}
        return self.evaluation_id

    def create_datapoint(self, *, eval_id, data, target, metadata):
        assert eval_id == self.evaluation_id
        self.created["datapoint"] = {"data": data, "target": target, "metadata": metadata}
        return self.datapoint_id

    def update_datapoint(self, *, eval_id, datapoint_id, scores, executor_output):
        self.updated = {
            "eval_id": eval_id,
            "datapoint_id": datapoint_id,
            "scores": scores,
            "executor_output": executor_output,
        }


class FakeSql:
    def query(self, sql, parameters=None):
        return [{"sql": sql, "parameters": parameters}]


class FakeSdk:
    last = None

    def __init__(self, *, base_url, project_api_key, port, timeout):
        self.init_args = {
            "base_url": base_url,
            "project_api_key": project_api_key,
            "port": port,
            "timeout": timeout,
        }
        self.evals = FakeEvals()
        self.sql = FakeSql()
        FakeSdk.last = self


class BlankErrorEvals:
    def create_evaluation(self, *, name, metadata):
        raise RuntimeError()


class BlankErrorSdk:
    def __init__(self, *, base_url, project_api_key, port, timeout):
        self.evals = BlankErrorEvals()


def test_unconfigured_laminar_client_returns_error():
    client = laminar_client.LaminarClient(base_url="http://localhost", project_api_key="", http_port=8000, timeout_seconds=30)

    refs = client.create_eval_datapoint(name="eval", data={}, target={}, metadata={})

    assert refs.configured is False
    assert refs.error


def test_laminar_client_uses_sdk_evals(monkeypatch):
    monkeypatch.setattr(laminar_client, "LmnrSdkClient", FakeSdk)
    client = laminar_client.LaminarClient(base_url="http://localhost", project_api_key="key", http_port=8000, timeout_seconds=30)

    refs = client.create_eval_datapoint(name="eval", data={"case": 1}, target={"pass": True}, metadata={"run": "r1"})
    error = client.update_datapoint(
        refs=refs,
        executor_output={"steps": []},
        scores={"passed": 1},
        metadata={"run": "r1", "step_results": [{"actual": "large result"}]},
    )

    assert error is None
    assert FakeSdk.last.init_args["base_url"] == "http://localhost"
    assert FakeSdk.last.init_args["port"] == 8000
    assert UUID(refs.evaluation_id) == FakeSdk.last.evals.evaluation_id
    assert FakeSdk.last.evals.updated["scores"] == {"passed": 1}
    assert FakeSdk.last.evals.updated["executor_output"]["metadata"] == {"run": "r1"}


def test_laminar_client_reports_blank_sdk_errors(monkeypatch):
    monkeypatch.setattr(laminar_client, "LmnrSdkClient", BlankErrorSdk)
    client = laminar_client.LaminarClient(base_url="http://localhost", project_api_key="key", http_port=8000, timeout_seconds=30)

    refs = client.create_eval_datapoint(name="eval", data={}, target={}, metadata={})

    assert refs.configured is True
    assert refs.error
    assert "初始化 Laminar 测评记录失败" in refs.error
    assert "RuntimeError" in refs.error
    assert "http://localhost:8000" in refs.error
