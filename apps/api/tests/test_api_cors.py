from fastapi.testclient import TestClient

from skillhub.api.database import resolve_database_url
from skillhub.api.main import create_app, create_postgres_engine


def test_cors_allows_private_lan_browser_origins():
    engine = create_postgres_engine(resolve_database_url())
    client = TestClient(create_app(engine))

    response = client.options(
        "/api/skills",
        headers={
            "Origin": "http://192.168.1.20:3030",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://192.168.1.20:3030"
    engine.dispose()


def test_cors_allows_lan_hostnames_and_private_network_preflight():
    engine = create_postgres_engine(resolve_database_url())
    client = TestClient(create_app(engine))

    response = client.options(
        "/api/skills",
        headers={
            "Origin": "http://skillhub-office-lan:3030",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Private-Network": "true",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://skillhub-office-lan:3030"
    assert response.headers["access-control-allow-private-network"] == "true"
    engine.dispose()


def test_cors_allows_custom_origin_list(monkeypatch):
    monkeypatch.setenv("SKILLHUB_CORS_ALLOW_ORIGINS", "http://skillhub.test:3030")
    engine = create_postgres_engine(resolve_database_url())
    client = TestClient(create_app(engine))

    response = client.options(
        "/api/skills",
        headers={
            "Origin": "http://skillhub.test:3030",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://skillhub.test:3030"
    engine.dispose()
