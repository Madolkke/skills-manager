from __future__ import annotations

import pytest

from skillhub.models.schema import database


def test_postgres_engine_configures_connect_statement_and_lock_timeouts(monkeypatch) -> None:
    captured = {}

    def fake_create_engine(url, **kwargs):
        captured.update({"url": url, **kwargs})
        return object()

    monkeypatch.setattr(database, "create_engine", fake_create_engine)
    environment = {
        "SKILLHUB_DATABASE_CONNECT_TIMEOUT_SECONDS": "7",
        "SKILLHUB_DATABASE_STATEMENT_TIMEOUT_MS": "8000",
        "SKILLHUB_DATABASE_LOCK_TIMEOUT_MS": "900",
    }

    database.create_postgres_engine("postgresql+psycopg://localhost/test", environment)

    assert captured["connect_args"] == {
        "connect_timeout": 7,
        "options": "-c statement_timeout=8000 -c lock_timeout=900",
    }


@pytest.mark.parametrize(
    "name,value",
    [
        ("SKILLHUB_DATABASE_CONNECT_TIMEOUT_SECONDS", "0"),
        ("SKILLHUB_DATABASE_STATEMENT_TIMEOUT_MS", "invalid"),
        ("SKILLHUB_DATABASE_LOCK_TIMEOUT_MS", "-1"),
    ],
)
def test_postgres_engine_rejects_invalid_timeout_configuration(name: str, value: str) -> None:
    with pytest.raises(ValueError, match=name):
        database.create_postgres_engine("postgresql+psycopg://localhost/test", {name: value})
