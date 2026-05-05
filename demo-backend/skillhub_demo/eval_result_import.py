from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping


SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schemas" / "eval-result-import.schema.json"


def load_eval_result_import_schema() -> Dict[str, Any]:
    with SCHEMA_PATH.open("r", encoding="utf-8") as file:
        value = json.load(file)
    if not isinstance(value, dict):
        raise ValueError("Eval result import schema must be a JSON object")
    return value


def validate_eval_result_import_shape(payload: Mapping[str, Any]) -> None:
    required = ["variant_version_id", "eval_set_version_id", "strategy_ref", "results"]
    for key in required:
        value = payload.get(key)
        if key == "results":
            continue
        if not isinstance(value, str) or not value:
            raise ValueError("Missing required field: %s" % key)

    results = payload.get("results")
    if not isinstance(results, dict):
        raise ValueError("results must be an object mapping case version id to boolean")
    if not results:
        raise ValueError("results must include at least one case version result")
    if not all(isinstance(key, str) and key for key in results.keys()):
        raise ValueError("results keys must be non-empty case version ids")
    if not all(isinstance(value, bool) for value in results.values()):
        raise ValueError("results values must be booleans")

    run_config_hash = payload.get("run_config_hash")
    if run_config_hash is not None and (not isinstance(run_config_hash, str) or not run_config_hash):
        raise ValueError("run_config_hash must be a non-empty string when provided")

    config = payload.get("config")
    if config is not None and not isinstance(config, dict):
        raise ValueError("config must be an object when provided")

    metadata = payload.get("metadata")
    if metadata is not None and not isinstance(metadata, dict):
        raise ValueError("metadata must be an object when provided")
