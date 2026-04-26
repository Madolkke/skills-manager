from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, Dict, List, Type, TypeVar, Union

from .models import (
    AppData,
    Artifact,
    CaseResult,
    ContentRef,
    EvalCase,
    EvalCorpus,
    EvalRun,
    EvalSetVersion,
    Skill,
    TagSet,
    Variant,
    VariantVersion,
    to_jsonable,
)


PathLike = Union[str, Path]
T = TypeVar("T")


def load_app_data(path: PathLike, fallback: Callable[[], AppData]) -> AppData:
    data_path = Path(path)
    if not data_path.exists():
        return fallback()
    with data_path.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)
    if not isinstance(raw, dict):
        return fallback()
    return app_data_from_dict(raw)


def save_app_data(path: PathLike, data: AppData) -> None:
    data_path = Path(path)
    data_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = data_path.with_suffix(data_path.suffix + ".tmp")
    with temp_path.open("w", encoding="utf-8") as handle:
        json.dump(to_jsonable(data), handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    temp_path.replace(data_path)


def app_data_from_dict(raw: Dict[str, object]) -> AppData:
    return AppData(
        skills=_items(raw, "skills", Skill),
        tag_sets=_items(raw, "tag_sets", TagSet),
        variants=_items(raw, "variants", Variant),
        variant_versions=[_variant_version(item) for item in _dicts(raw, "variant_versions")],
        eval_corpora=_items(raw, "eval_corpora", EvalCorpus),
        eval_cases=_items(raw, "eval_cases", EvalCase),
        eval_set_versions=_items(raw, "eval_set_versions", EvalSetVersion),
        eval_runs=_items(raw, "eval_runs", EvalRun),
        case_results=_items(raw, "case_results", CaseResult),
        artifacts=_items(raw, "artifacts", Artifact),
    )


def _items(raw: Dict[str, object], key: str, item_type: Type[T]) -> List[T]:
    return [item_type(**item) for item in _dicts(raw, key)]  # type: ignore[arg-type]


def _variant_version(raw: Dict[str, object]) -> VariantVersion:
    content_ref = raw.get("content_ref")
    if not isinstance(content_ref, dict):
        raise ValueError("variant_version.content_ref must be an object")
    return VariantVersion(
        id=str(raw["id"]),
        variant_ref=str(raw["variant_ref"]),
        version=str(raw["version"]),
        content_ref=ContentRef(**content_ref),
        change_note=raw.get("change_note") if isinstance(raw.get("change_note"), str) else None,
        created_at=str(raw["created_at"]),
    )


def _dicts(raw: Dict[str, object], key: str) -> List[Dict[str, object]]:
    value = raw.get(key, [])
    if not isinstance(value, list):
        raise ValueError("%s must be a list" % key)
    if not all(isinstance(item, dict) for item in value):
        raise ValueError("%s must contain objects" % key)
    return value
