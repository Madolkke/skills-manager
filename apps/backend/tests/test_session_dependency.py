from __future__ import annotations

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from skillhub.views.dependencies import session_dependency


class _FailingTransaction:
    def __enter__(self):
        return object()

    def __exit__(self, exc_type, exc, traceback):
        if exc_type is None:
            raise RuntimeError("commit failed")
        return False


class _FailingSessionFactory:
    def begin(self) -> _FailingTransaction:
        return _FailingTransaction()


def test_function_scoped_session_commit_fails_before_response_is_sent() -> None:
    app = FastAPI()
    app.state.session_factory = _FailingSessionFactory()

    @app.get("/commit-failure")
    def endpoint(session=Depends(session_dependency, scope="function")):
        return {"ok": True, "session_active": session is not None}

    response = TestClient(app, raise_server_exceptions=False).get("/commit-failure")

    assert response.status_code == 500
    assert response.text == "Internal Server Error"
