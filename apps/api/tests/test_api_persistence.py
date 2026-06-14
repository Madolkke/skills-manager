from fastapi.testclient import TestClient
import pytest

from skillhub.api.main import create_app, create_postgres_engine, resolve_database_url
from skillhub.infrastructure.db.tables import metadata


def test_resolve_database_url_requires_configured_postgresql(monkeypatch):
    monkeypatch.delenv("SKILLHUB_DATABASE_URL", raising=False)

    with pytest.raises(ValueError, match="SKILLHUB_DATABASE_URL"):
        resolve_database_url()


def test_resolve_database_url_rejects_non_postgresql(monkeypatch):
    monkeypatch.setenv("SKILLHUB_DATABASE_URL", "sqlite:///:memory:")

    with pytest.raises(ValueError, match="postgresql"):
        resolve_database_url()


def test_postgres_engine_persists_skill_between_app_instances():
    database_url = resolve_database_url()
    first_engine = create_postgres_engine(database_url)
    metadata.drop_all(first_engine)
    metadata.create_all(first_engine)
    first_client = TestClient(create_app(first_engine))
    response = first_client.post(
        "/api/skills",
        json={
            "slug": "persistent-reviewer",
            "owner_ref": "skillhub-lab",
            "content_ref": {
                "kind": "skill_bundle",
                "locator": "memory:persistent-reviewer",
                "digest": "digest-persistent",
            },
            "change_summary": "Initial persistent skill.",
        },
    )
    assert response.status_code == 200
    first_engine.dispose()

    second_engine = create_postgres_engine(database_url)
    second_client = TestClient(create_app(second_engine))

    skills = second_client.get("/api/skills").json()

    assert [item["skill"]["slug"] for item in skills] == ["persistent-reviewer"]
    metadata.drop_all(second_engine)
    second_engine.dispose()
