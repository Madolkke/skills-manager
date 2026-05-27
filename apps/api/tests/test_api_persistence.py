from pathlib import Path
import sqlite3

from fastapi.testclient import TestClient

from skillhub.api.main import create_app, create_sqlite_engine, resolve_database_url


def test_create_app_defaults_to_file_sqlite_database(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("SKILLHUB_DATABASE_URL", raising=False)
    monkeypatch.setenv("SKILLHUB_DATA_DIR", str(tmp_path))

    app = create_app()
    app.state.engine.dispose()

    assert resolve_database_url().startswith("sqlite:///")
    assert (tmp_path / "skillhub.sqlite3").exists()


def test_sqlite_engine_persists_skill_between_app_instances(tmp_path: Path):
    database_url = f"sqlite:///{tmp_path / 'skillhub.sqlite3'}"
    first_engine = create_sqlite_engine(database_url)
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

    second_engine = create_sqlite_engine(database_url)
    second_client = TestClient(create_app(second_engine))

    skills = second_client.get("/api/skills").json()

    assert [item["skill"]["slug"] for item in skills] == ["persistent-reviewer"]


def test_sqlite_startup_backfills_old_version_pointer_schema(tmp_path: Path):
    database_path = tmp_path / "skillhub.sqlite3"
    with sqlite3.connect(database_path) as connection:
        connection.executescript(
            """
            create table skills (
              id text primary key,
              slug text not null unique,
              owner_ref text not null,
              lifecycle_status text not null default 'active',
              created_at text not null,
              updated_at text not null
            );
            create table skill_versions (
              id text primary key,
              skill_id text not null,
              version_number integer not null,
              content_ref text not null,
              content_digest text not null,
              change_summary text not null,
              created_at text not null,
              created_by text not null
            );
            create table eval_sets (
              id text primary key,
              skill_id text not null,
              name text not null,
              description text not null default '',
              lifecycle_status text not null default 'active',
              created_at text not null,
              updated_at text not null
            );
            create table eval_set_versions (
              id text primary key,
              skill_id text not null,
              eval_set_id text not null,
              version_number integer not null,
              created_at text not null,
              created_by text not null
            );
            insert into skills values ('skill_old', 'old-reviewer', 'owner', 'active', '2026-01-01', '2026-01-01');
            insert into skill_versions values ('skillver_old', 'skill_old', 1, '{"kind":"skill_bundle","locator":"memory:old","digest":"digest-old"}', 'digest-old', 'Initial.', '2026-01-01', 'owner');
            insert into eval_sets values ('evalset_old', 'skill_old', 'Primary', 'Primary regression suite', 'active', '2026-01-01', '2026-01-01');
            insert into eval_set_versions values ('evalsetver_old', 'skill_old', 'evalset_old', 1, '2026-01-01', 'owner');
            """
        )

    engine = create_sqlite_engine(f"sqlite:///{database_path}")
    client = TestClient(create_app(engine))

    skills = client.get("/api/skills")

    assert skills.status_code == 200
    assert skills.json()[0]["skill"]["current_version_id"] == "skillver_old"
    assert skills.json()[0]["summary"]["primary_eval_set"]["current_version_id"] == "evalsetver_old"
    assert skills.json()[0]["summary"]["current_version"]["display_name"] is None
    engine.dispose()
