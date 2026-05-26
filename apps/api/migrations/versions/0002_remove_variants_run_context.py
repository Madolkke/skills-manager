"""Move SkillHub versioning from variants to skill versions.

Revision ID: 0002_remove_variants_run_context
Revises: 0001_initial_schema
Create Date: 2026-05-26
"""

from __future__ import annotations

from hashlib import sha256
import json

from alembic import op
import sqlalchemy as sa


revision = "0002_remove_variants_run_context"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "skill_versions" in tables and "variant_versions" not in tables:
        return
    if "variant_versions" not in tables:
        return

    op.create_table(
        "skill_versions",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("skill_id", sa.Text(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("content_ref", sa.JSON(), nullable=False),
        sa.Column("content_digest", sa.Text(), nullable=False),
        sa.Column("change_summary", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Text(), nullable=False),
        sa.CheckConstraint("version_number > 0", name="skill_versions_version_number_positive"),
        sa.UniqueConstraint("skill_id", "version_number", name="skill_versions_skill_version_unique"),
        sa.UniqueConstraint("id", "skill_id", name="skill_versions_id_skill_unique"),
    )
    op.execute(
        """
        insert into skill_versions (id, skill_id, version_number, content_ref, content_digest, change_summary, created_at, created_by)
        select id,
               skill_id,
               row_number() over (partition by skill_id order by created_at, id) as version_number,
               content_ref,
               content_digest,
               change_summary,
               created_at,
               created_by
        from variant_versions
        """
    )
    op.add_column("skills", sa.Column("current_version_id", sa.Text(), nullable=True))
    op.execute(
        """
        update skills
        set current_version_id = (
          select variants.current_version_id
          from variants
          where variants.id = skills.default_variant_id
        )
        """
    )
    if "eval_runs" in tables:
        _add_eval_run_context_columns()
        _backfill_eval_run_context(bind)
    if "accepted_verifications" in tables:
        _backfill_accepted_verifications(bind)
    op.create_index("skill_versions_skill_id_idx", "skill_versions", ["skill_id"])
    op.create_index("eval_runs_skill_version_id_idx", "eval_runs", ["skill_version_id"])
    op.create_index("eval_runs_context_hash_idx", "eval_runs", ["run_context_hash"])
    op.create_index(
        "accepted_verifications_context_idx",
        "accepted_verifications",
        ["skill_id", "skill_version_id", "eval_set_version_id", "run_context_hash"],
    )


def downgrade() -> None:
    raise RuntimeError("Variant removal migration cannot be downgraded without data loss.")


def _add_eval_run_context_columns() -> None:
    op.add_column("eval_runs", sa.Column("skill_version_id", sa.Text(), nullable=True))
    op.add_column("eval_runs", sa.Column("environment_tags", sa.JSON(), nullable=True))
    op.add_column("eval_runs", sa.Column("run_context", sa.JSON(), nullable=True))
    op.add_column("eval_runs", sa.Column("run_context_hash", sa.Text(), nullable=True))
    op.execute("update eval_runs set skill_version_id = variant_version_id")


def _backfill_eval_run_context(bind) -> None:
    rows = bind.execute(
        sa.text(
            """
            select eval_runs.id as run_id, coalesce(tag_sets.tags, '[]') as tags
            from eval_runs
            join variant_versions on variant_versions.id = eval_runs.variant_version_id
            join variants on variants.id = variant_versions.variant_id
            left join tag_sets on tag_sets.id = variants.tag_set_id
            """
        )
    ).mappings()
    for row in rows:
        tags = _coerce_tags(row["tags"])
        context_hash = _context_hash(tags, {})
        bind.execute(
            sa.text(
                """
                update eval_runs
                set environment_tags = :tags,
                    run_context = :context,
                    run_context_hash = :context_hash
                where id = :run_id
                """
            ),
            {"run_id": row["run_id"], "tags": json.dumps(tags), "context": json.dumps({}), "context_hash": context_hash},
        )


def _backfill_accepted_verifications(bind) -> None:
    rows = bind.execute(
        sa.text(
            """
            select accepted_verifications.id as verification_id,
                   accepted_verifications.variant_version_id as skill_version_id,
                   eval_runs.run_context_hash as run_context_hash
            from accepted_verifications
            join eval_runs on eval_runs.id = accepted_verifications.eval_run_id
            """
        )
    ).mappings()
    op.add_column("accepted_verifications", sa.Column("skill_version_id", sa.Text(), nullable=True))
    op.add_column("accepted_verifications", sa.Column("run_context_hash", sa.Text(), nullable=True))
    for row in rows:
        bind.execute(
            sa.text(
                """
                update accepted_verifications
                set skill_version_id = :skill_version_id,
                    run_context_hash = :run_context_hash
                where id = :verification_id
                """
            ),
            {
                "verification_id": row["verification_id"],
                "skill_version_id": row["skill_version_id"],
                "run_context_hash": row["run_context_hash"],
            },
        )


def _coerce_tags(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return sorted({str(item).strip() for item in value if str(item).strip()})
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            parsed = [value]
        return _coerce_tags(parsed)
    return []


def _context_hash(environment_tags: list[str], run_context: dict[str, object]) -> str:
    payload = {"environment_tags": environment_tags, "run_context": run_context}
    return sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
