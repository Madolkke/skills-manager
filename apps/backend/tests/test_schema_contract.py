from pathlib import Path

from sqlalchemy import ForeignKeyConstraint, UniqueConstraint
from sqlalchemy.orm import RelationshipProperty

from skillhub.models.schema import Base, metadata
from skillhub.models.schema.evaluations import EvalCase, EvalRun, EvalSet
from skillhub.models.schema.migrations import expected_revision
from skillhub.models.schema.skills import Skill, SkillVersion

BACKEND_ROOT = Path(__file__).parents[1]


def test_declarative_metadata_is_the_only_schema_definition() -> None:
    schema_root = BACKEND_ROOT / "skillhub" / "models" / "schema"
    assert not (schema_root / "schema.sql").exists()
    assert not (schema_root / "sync.py").exists()
    assert metadata is Base.metadata


def test_alembic_head_is_the_declarative_baseline() -> None:
    assert expected_revision() == "0002_seed_publish_targets"
    revision = BACKEND_ROOT / "migrations" / "versions" / "0001_orm_baseline_declarative_orm_baseline.py"
    source = revision.read_text(encoding="utf-8")
    for table_name in metadata.tables:
        assert f"op.create_table('{table_name}'" in source


def test_skill_relationships_are_explicit_and_raise_on_implicit_load() -> None:
    relationships = Skill.__mapper__.relationships
    for name in ("versions", "current_version", "eval_sets", "eval_cases", "workflow", "saved_views"):
        relation = relationships[name]
        assert isinstance(relation, RelationshipProperty)
        assert relation.lazy == "raise"
    assert SkillVersion.__mapper__.relationships["skill"].back_populates == "versions"


def test_evaluation_relationships_are_bidirectional() -> None:
    assert EvalSet.__mapper__.relationships["skill"].back_populates == "eval_sets"
    assert EvalCase.__mapper__.relationships["skill"].back_populates == "eval_cases"
    assert EvalRun.__mapper__.relationships["eval_set"].back_populates == "runs"


def test_all_relationships_are_explicitly_bidirectional_and_raise_on_load() -> None:
    for mapper in Base.registry.mappers:
        for relation in mapper.relationships:
            assert relation.back_populates is not None, f"{mapper.class_.__name__}.{relation.key} has no back_populates"
            assert relation.lazy == "raise", f"{mapper.class_.__name__}.{relation.key} permits implicit SQL"


def test_cross_skill_invariants_remain_database_constraints() -> None:
    eval_run_constraints = metadata.tables["eval_runs"].constraints
    foreign_keys = {constraint.name for constraint in eval_run_constraints if isinstance(constraint, ForeignKeyConstraint)}
    assert "eval_runs_skill_version_skill_fkey" in foreign_keys
    assert "eval_runs_eval_set_skill_fkey" in foreign_keys

    version_constraints = metadata.tables["skill_versions"].constraints
    unique_constraints = {constraint.name for constraint in version_constraints if isinstance(constraint, UniqueConstraint)}
    assert "skill_versions_skill_version_unique" in unique_constraints
    assert "skill_versions_skill_semver_unique" in unique_constraints
