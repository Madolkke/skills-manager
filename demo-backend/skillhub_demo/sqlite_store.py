from __future__ import annotations

import json
import sqlite3
from typing import Any, Dict, Iterable, Tuple

from .models import AppData, to_jsonable
from .persistence import app_data_from_dict


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS skills (
  id TEXT PRIMARY KEY,
  slug TEXT NOT NULL UNIQUE,
  owner_ref TEXT NOT NULL,
  default_variant_ref TEXT,
  created_at TEXT NOT NULL,
  FOREIGN KEY (default_variant_ref) REFERENCES variants(id)
);

CREATE TABLE IF NOT EXISTS tag_sets (
  id TEXT PRIMARY KEY,
  tags_hash TEXT NOT NULL UNIQUE,
  tags_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS artifacts (
  id TEXT PRIMARY KEY,
  kind TEXT NOT NULL,
  content TEXT NOT NULL,
  content_hash TEXT NOT NULL,
  media_type TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS variants (
  id TEXT PRIMARY KEY,
  skill_ref TEXT NOT NULL,
  name TEXT NOT NULL,
  label TEXT NOT NULL,
  summary TEXT NOT NULL,
  tag_set_ref TEXT NOT NULL,
  current_version_ref TEXT,
  created_at TEXT NOT NULL,
  FOREIGN KEY (skill_ref) REFERENCES skills(id),
  FOREIGN KEY (tag_set_ref) REFERENCES tag_sets(id),
  FOREIGN KEY (current_version_ref) REFERENCES variant_versions(id)
);

CREATE TABLE IF NOT EXISTS variant_versions (
  id TEXT PRIMARY KEY,
  variant_ref TEXT NOT NULL,
  version TEXT NOT NULL,
  content_kind TEXT NOT NULL,
  content_locator TEXT NOT NULL,
  content_digest TEXT NOT NULL,
  content_path TEXT,
  change_note TEXT,
  created_at TEXT NOT NULL,
  FOREIGN KEY (variant_ref) REFERENCES variants(id),
  UNIQUE (variant_ref, version)
);

CREATE TABLE IF NOT EXISTS eval_corpora (
  id TEXT PRIMARY KEY,
  skill_ref TEXT NOT NULL UNIQUE,
  created_at TEXT NOT NULL,
  FOREIGN KEY (skill_ref) REFERENCES skills(id)
);

CREATE TABLE IF NOT EXISTS eval_cases (
  id TEXT PRIMARY KEY,
  corpus_ref TEXT NOT NULL,
  title TEXT NOT NULL,
  source_type TEXT NOT NULL,
  input_artifact_ref TEXT NOT NULL,
  expectation_artifact_ref TEXT NOT NULL,
  grader_ref TEXT NOT NULL,
  expectation TEXT NOT NULL,
  origin_ref TEXT,
  created_at TEXT NOT NULL,
  FOREIGN KEY (corpus_ref) REFERENCES eval_corpora(id),
  FOREIGN KEY (input_artifact_ref) REFERENCES artifacts(id),
  FOREIGN KEY (expectation_artifact_ref) REFERENCES artifacts(id)
);

CREATE TABLE IF NOT EXISTS eval_set_versions (
  id TEXT PRIMARY KEY,
  corpus_ref TEXT NOT NULL,
  version TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (corpus_ref) REFERENCES eval_corpora(id),
  UNIQUE (corpus_ref, version)
);

CREATE TABLE IF NOT EXISTS eval_set_cases (
  eval_set_version_ref TEXT NOT NULL,
  case_ref TEXT NOT NULL,
  position INTEGER NOT NULL,
  PRIMARY KEY (eval_set_version_ref, case_ref),
  FOREIGN KEY (eval_set_version_ref) REFERENCES eval_set_versions(id),
  FOREIGN KEY (case_ref) REFERENCES eval_cases(id)
);

CREATE TABLE IF NOT EXISTS eval_runs (
  id TEXT PRIMARY KEY,
  variant_version_ref TEXT NOT NULL,
  eval_set_version_ref TEXT NOT NULL,
  strategy_ref TEXT NOT NULL,
  run_config_hash TEXT NOT NULL,
  status TEXT NOT NULL,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  result_artifact_ref TEXT,
  FOREIGN KEY (variant_version_ref) REFERENCES variant_versions(id),
  FOREIGN KEY (eval_set_version_ref) REFERENCES eval_set_versions(id),
  FOREIGN KEY (result_artifact_ref) REFERENCES artifacts(id)
);

CREATE TABLE IF NOT EXISTS case_results (
  run_ref TEXT NOT NULL,
  case_ref TEXT NOT NULL,
  passed INTEGER NOT NULL CHECK (passed IN (0, 1)),
  score INTEGER NOT NULL,
  PRIMARY KEY (run_ref, case_ref),
  FOREIGN KEY (run_ref) REFERENCES eval_runs(id),
  FOREIGN KEY (case_ref) REFERENCES eval_cases(id)
);

CREATE TABLE IF NOT EXISTS app_state (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  state_json TEXT NOT NULL,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


def connect(path: str = ":memory:") -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize(connection: sqlite3.Connection) -> None:
    connection.executescript(SCHEMA)


def import_app_data(connection: sqlite3.Connection, data: AppData) -> None:
    initialize(connection)
    with connection:
        _insert_tag_sets(connection, data)
        _insert_artifacts(connection, data)
        _insert_skills_without_default(connection, data)
        _insert_variants_without_current(connection, data)
        _insert_variant_versions(connection, data)
        _update_variant_current_versions(connection, data)
        _update_skill_default_variants(connection, data)
        _insert_eval_corpora(connection, data)
        _insert_eval_cases(connection, data)
        _insert_eval_set_versions(connection, data)
        _insert_eval_runs(connection, data)
        _insert_case_results(connection, data)


def replace_app_data(connection: sqlite3.Connection, data: AppData) -> None:
    initialize(connection)
    _drop_domain_tables(connection)
    import_app_data(connection, data)


def save_app_snapshot(connection: sqlite3.Connection, data: AppData) -> None:
    replace_app_data(connection, data)
    state_json = json.dumps(to_jsonable(data), ensure_ascii=False, sort_keys=True)
    with connection:
        connection.execute(
            """
            INSERT INTO app_state (id, state_json, updated_at)
            VALUES (1, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(id) DO UPDATE SET state_json = excluded.state_json, updated_at = CURRENT_TIMESTAMP
            """,
            (state_json,),
        )


def load_app_snapshot(connection: sqlite3.Connection) -> AppData | None:
    initialize(connection)
    row = connection.execute("SELECT state_json FROM app_state WHERE id = 1").fetchone()
    if row is None:
        return None
    raw = json.loads(row["state_json"])
    if not isinstance(raw, dict):
        raise ValueError("SQLite app_state.state_json must be an object")
    return app_data_from_dict(raw)


def eval_result_counts(connection: sqlite3.Connection, variant_version_id: str, eval_set_version_id: str) -> Dict[str, int]:
    rows = connection.execute(
        """
        SELECT esc.case_ref, cr.passed
        FROM eval_set_cases esc
        LEFT JOIN eval_runs er
          ON er.eval_set_version_ref = esc.eval_set_version_ref
         AND er.variant_version_ref = ?
         AND er.status = 'finished'
        LEFT JOIN case_results cr
          ON cr.run_ref = er.id
         AND cr.case_ref = esc.case_ref
        WHERE esc.eval_set_version_ref = ?
        ORDER BY esc.position
        """,
        (variant_version_id, eval_set_version_id),
    ).fetchall()
    counts = {"passed": 0, "failed": 0, "missing": 0, "total": len(rows)}
    for row in rows:
        if row["passed"] is None:
            counts["missing"] += 1
        elif row["passed"]:
            counts["passed"] += 1
        else:
            counts["failed"] += 1
    return counts


def eval_set_case_details(connection: sqlite3.Connection, eval_set_version_id: str) -> Iterable[Dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT ec.id, ec.title, input.content AS input, expected.content AS expected_output
        FROM eval_set_cases esc
        JOIN eval_cases ec ON ec.id = esc.case_ref
        JOIN artifacts input ON input.id = ec.input_artifact_ref
        JOIN artifacts expected ON expected.id = ec.expectation_artifact_ref
        WHERE esc.eval_set_version_ref = ?
        ORDER BY esc.position
        """,
        (eval_set_version_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def _drop_domain_tables(connection: sqlite3.Connection) -> None:
    tables: Tuple[str, ...] = (
        "case_results",
        "eval_runs",
        "eval_set_cases",
        "eval_set_versions",
        "eval_cases",
        "eval_corpora",
        "variant_versions",
        "variants",
        "skills",
        "tag_sets",
        "artifacts",
    )
    with connection:
        connection.execute("PRAGMA foreign_keys = OFF")
        for table in tables:
            connection.execute("DROP TABLE IF EXISTS %s" % table)
        connection.execute("PRAGMA foreign_keys = ON")


def _insert_tag_sets(connection: sqlite3.Connection, data: AppData) -> None:
    connection.executemany(
        "INSERT INTO tag_sets (id, tags_hash, tags_json) VALUES (?, ?, ?)",
        [(item.id, item.tags_hash, json.dumps(item.tags, ensure_ascii=False)) for item in data.tag_sets],
    )


def _insert_artifacts(connection: sqlite3.Connection, data: AppData) -> None:
    connection.executemany(
        """
        INSERT INTO artifacts (id, kind, content, content_hash, media_type, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        [(item.id, item.kind, item.content, item.content_hash, item.media_type, item.created_at) for item in data.artifacts],
    )


def _insert_skills_without_default(connection: sqlite3.Connection, data: AppData) -> None:
    connection.executemany(
        """
        INSERT INTO skills (id, slug, owner_ref, default_variant_ref, created_at)
        VALUES (?, ?, ?, NULL, ?)
        """,
        [(item.id, item.slug, item.owner_ref, item.created_at) for item in data.skills],
    )


def _insert_variants_without_current(connection: sqlite3.Connection, data: AppData) -> None:
    connection.executemany(
        """
        INSERT INTO variants (id, skill_ref, name, label, summary, tag_set_ref, current_version_ref, created_at)
        VALUES (?, ?, ?, ?, ?, ?, NULL, ?)
        """,
        [(item.id, item.skill_ref, item.name, item.label, item.summary, item.tag_set_ref, item.created_at) for item in data.variants],
    )


def _insert_variant_versions(connection: sqlite3.Connection, data: AppData) -> None:
    connection.executemany(
        """
        INSERT INTO variant_versions
          (id, variant_ref, version, content_kind, content_locator, content_digest, content_path, change_note, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                item.id,
                item.variant_ref,
                item.version,
                item.content_ref.kind,
                item.content_ref.locator,
                item.content_ref.digest,
                item.content_ref.path,
                item.change_note,
                item.created_at,
            )
            for item in data.variant_versions
        ],
    )


def _update_variant_current_versions(connection: sqlite3.Connection, data: AppData) -> None:
    connection.executemany(
        "UPDATE variants SET current_version_ref = ? WHERE id = ?",
        [(item.current_version_ref, item.id) for item in data.variants],
    )


def _update_skill_default_variants(connection: sqlite3.Connection, data: AppData) -> None:
    connection.executemany(
        "UPDATE skills SET default_variant_ref = ? WHERE id = ?",
        [(item.default_variant_ref, item.id) for item in data.skills],
    )


def _insert_eval_corpora(connection: sqlite3.Connection, data: AppData) -> None:
    connection.executemany(
        "INSERT INTO eval_corpora (id, skill_ref, created_at) VALUES (?, ?, ?)",
        [(item.id, item.skill_ref, item.created_at) for item in data.eval_corpora],
    )


def _insert_eval_cases(connection: sqlite3.Connection, data: AppData) -> None:
    connection.executemany(
        """
        INSERT INTO eval_cases
          (id, corpus_ref, title, source_type, input_artifact_ref, expectation_artifact_ref, grader_ref, expectation, origin_ref, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                item.id,
                item.corpus_ref,
                item.title,
                item.source_type,
                item.input_artifact_ref,
                item.expectation_artifact_ref,
                item.grader_ref,
                item.expectation,
                item.origin_ref,
                item.created_at,
            )
            for item in data.eval_cases
        ],
    )


def _insert_eval_set_versions(connection: sqlite3.Connection, data: AppData) -> None:
    connection.executemany(
        "INSERT INTO eval_set_versions (id, corpus_ref, version, created_at) VALUES (?, ?, ?, ?)",
        [(item.id, item.corpus_ref, item.version, item.created_at) for item in data.eval_set_versions],
    )
    connection.executemany(
        "INSERT INTO eval_set_cases (eval_set_version_ref, case_ref, position) VALUES (?, ?, ?)",
        [
            (item.id, case_ref, index)
            for item in data.eval_set_versions
            for index, case_ref in enumerate(item.case_refs)
        ],
    )


def _insert_eval_runs(connection: sqlite3.Connection, data: AppData) -> None:
    connection.executemany(
        """
        INSERT INTO eval_runs
          (id, variant_version_ref, eval_set_version_ref, strategy_ref, run_config_hash, status, started_at, finished_at, result_artifact_ref)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                item.id,
                item.variant_version_ref,
                item.eval_set_version_ref,
                item.strategy_ref,
                item.run_config_hash,
                item.status,
                item.started_at,
                item.finished_at,
                item.result_artifact_ref,
            )
            for item in data.eval_runs
        ],
    )


def _insert_case_results(connection: sqlite3.Connection, data: AppData) -> None:
    connection.executemany(
        "INSERT INTO case_results (run_ref, case_ref, passed, score) VALUES (?, ?, ?, ?)",
        [(item.run_ref, item.case_ref, int(item.passed), item.score) for item in data.case_results],
    )


def table_counts(connection: sqlite3.Connection) -> Dict[str, int]:
    tables: Tuple[str, ...] = (
        "skills",
        "tag_sets",
        "variants",
        "variant_versions",
        "eval_corpora",
        "eval_cases",
        "eval_set_versions",
        "eval_set_cases",
        "eval_runs",
        "case_results",
        "artifacts",
    )
    return {
        table: connection.execute("SELECT COUNT(*) AS count FROM %s" % table).fetchone()["count"]
        for table in tables
    }
