from fastapi.testclient import TestClient

from skillhub.api.main import create_app, create_sqlite_engine


def test_cors_allows_private_lan_browser_origins():
    engine = create_sqlite_engine("sqlite:///:memory:")
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


def test_cors_allows_custom_origin_list(monkeypatch):
    monkeypatch.setenv("SKILLHUB_CORS_ALLOW_ORIGINS", "http://skillhub.test:3030")
    engine = create_sqlite_engine("sqlite:///:memory:")
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
