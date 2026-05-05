import unittest

from sqlalchemy import create_engine, event, select

from skillhub.domain.errors import InvariantError, NotFoundError
from skillhub.domain.models import ContentRef
from skillhub.infrastructure.db.repositories import SqlSkillRepository
from skillhub.infrastructure.db.tables import (
    artifacts,
    eval_case_versions,
    eval_cases,
    eval_set_case_versions,
    eval_set_versions,
    eval_sets,
    metadata,
    skills,
    tag_sets,
    variant_versions,
    variants,
)


class SqlSkillRepositoryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        event.listen(self.engine, "connect", self.enable_sqlite_foreign_keys)
        metadata.create_all(self.engine)
        self.repository = SqlSkillRepository(self.engine)

    def enable_sqlite_foreign_keys(self, dbapi_connection, _connection_record) -> None:
        dbapi_connection.execute("pragma foreign_keys=on")

    def test_create_skill_writes_default_variant_current_version_and_primary_eval_set(self):
        result = self.repository.create_skill(
            slug="code-reviewer",
            owner_ref="skillhub-lab",
            variant_name="Variant A",
            variant_label="Baseline",
            variant_summary="Baseline maintained answer.",
            tags=["gpt5.4", "codex"],
            content_ref=ContentRef(kind="skill_bundle", locator="memory:bundle", digest="digest-bundle"),
            change_summary="Initial version.",
            actor="tester",
        )

        with self.engine.connect() as connection:
            skill = connection.execute(select(skills).where(skills.c.id == result.skill_id)).mappings().one()
            variant = connection.execute(select(variants).where(variants.c.id == result.variant_id)).mappings().one()
            version = connection.execute(select(variant_versions).where(variant_versions.c.id == result.variant_version_id)).mappings().one()
            eval_set = connection.execute(select(eval_sets).where(eval_sets.c.id == result.eval_set_id)).mappings().one()
            eval_set_version = connection.execute(select(eval_set_versions).where(eval_set_versions.c.id == result.eval_set_version_id)).mappings().one()

        self.assertEqual(skill["default_variant_id"], result.variant_id)
        self.assertEqual(variant["skill_id"], result.skill_id)
        self.assertEqual(variant["current_version_id"], result.variant_version_id)
        self.assertEqual(version["version_number"], 1)
        self.assertEqual(version["content_ref"]["kind"], "skill_bundle")
        self.assertEqual(eval_set["current_version_id"], result.eval_set_version_id)
        self.assertEqual(eval_set_version["version_number"], 1)

    def test_create_skill_reuses_normalized_tag_set(self):
        first = self.repository.create_skill(
            slug="code-reviewer",
            owner_ref="skillhub-lab",
            variant_name="Variant A",
            variant_label="Baseline",
            variant_summary="Baseline maintained answer.",
            tags=["codex", "gpt5.4"],
            content_ref=ContentRef(kind="skill_bundle", locator="memory:code", digest="digest-code"),
            change_summary="Initial code version.",
            actor="tester",
        )
        second = self.repository.create_skill(
            slug="security-reviewer",
            owner_ref="skillhub-lab",
            variant_name="Variant A",
            variant_label="Security",
            variant_summary="Security maintained answer.",
            tags=["gpt5.4", "codex", "codex"],
            content_ref=ContentRef(kind="skill_bundle", locator="memory:security", digest="digest-security"),
            change_summary="Initial security version.",
            actor="tester",
        )

        with self.engine.connect() as connection:
            tag_set_count = connection.execute(select(tag_sets.c.id)).all()

        self.assertEqual(first.tag_set_id, second.tag_set_id)
        self.assertEqual(len(tag_set_count), 1)

    def test_candidate_variant_version_does_not_move_current_pointer(self):
        skill = self.create_skill()

        candidate = self.repository.create_variant_version(
            variant_id=skill.variant_id,
            content_ref=ContentRef(kind="skill_bundle", locator="memory:candidate", digest="digest-candidate"),
            change_summary="Candidate version.",
            actor="tester",
            make_current=False,
        )

        with self.engine.connect() as connection:
            variant = connection.execute(select(variants).where(variants.c.id == skill.variant_id)).mappings().one()
            version = connection.execute(select(variant_versions).where(variant_versions.c.id == candidate.variant_version_id)).mappings().one()

        self.assertEqual(candidate.version_number, 2)
        self.assertEqual(variant["current_version_id"], skill.variant_version_id)
        self.assertEqual(version["change_summary"], "Candidate version.")

    def test_make_current_variant_version_moves_current_pointer(self):
        skill = self.create_skill()

        created = self.repository.create_variant_version(
            variant_id=skill.variant_id,
            content_ref=ContentRef(kind="skill_bundle", locator="memory:v2", digest="digest-v2"),
            change_summary="Make current.",
            actor="tester",
            make_current=True,
        )

        with self.engine.connect() as connection:
            variant = connection.execute(select(variants).where(variants.c.id == skill.variant_id)).mappings().one()

        self.assertEqual(variant["current_version_id"], created.variant_version_id)

    def test_promote_variant_version_moves_current_pointer_to_existing_version(self):
        skill = self.create_skill()
        candidate = self.repository.create_variant_version(
            variant_id=skill.variant_id,
            content_ref=ContentRef(kind="skill_bundle", locator="memory:candidate", digest="digest-candidate"),
            change_summary="Candidate version.",
            actor="tester",
            make_current=False,
        )

        self.repository.promote_variant_version(variant_id=skill.variant_id, version_id=candidate.variant_version_id)

        with self.engine.connect() as connection:
            variant = connection.execute(select(variants).where(variants.c.id == skill.variant_id)).mappings().one()

        self.assertEqual(variant["current_version_id"], candidate.variant_version_id)

    def test_promote_rejects_version_from_another_variant(self):
        first = self.create_skill(slug="code-reviewer", digest="digest-code")
        second = self.create_skill(slug="security-reviewer", digest="digest-security")

        with self.assertRaisesRegex(InvariantError, "own version"):
            self.repository.promote_variant_version(
                variant_id=first.variant_id,
                version_id=second.variant_version_id,
            )

    def test_create_variant_version_requires_existing_variant(self):
        with self.assertRaisesRegex(NotFoundError, "Variant not found"):
            self.repository.create_variant_version(
                variant_id="missing",
                content_ref=ContentRef(kind="skill_bundle", locator="memory:v2", digest="digest-v2"),
                change_summary="Missing variant.",
                actor="tester",
                make_current=False,
            )

    def test_create_eval_case_creates_case_version_and_new_eval_set_snapshot(self):
        skill = self.create_skill()

        created = self.repository.create_eval_case(
            skill_id=skill.skill_id,
            title="PR: missing owner check",
            input_text="diff --git a/api.ts b/api.ts",
            expected_output="Should flag missing ownerId filter.",
            actor="tester",
        )

        with self.engine.connect() as connection:
            eval_case = connection.execute(select(eval_cases).where(eval_cases.c.id == created.eval_case_id)).mappings().one()
            case_version = connection.execute(select(eval_case_versions).where(eval_case_versions.c.id == created.eval_case_version_id)).mappings().one()
            eval_set = connection.execute(select(eval_sets).where(eval_sets.c.id == skill.eval_set_id)).mappings().one()
            membership = connection.execute(
                select(eval_set_case_versions)
                .where(eval_set_case_versions.c.eval_set_version_id == created.eval_set_version_id)
                .order_by(eval_set_case_versions.c.position)
            ).mappings().all()
            artifact_count = connection.execute(select(artifacts.c.id)).all()

        self.assertEqual(eval_case["current_version_id"], created.eval_case_version_id)
        self.assertEqual(case_version["case_id"], created.eval_case_id)
        self.assertEqual(case_version["version_number"], 1)
        self.assertEqual(eval_set["current_version_id"], created.eval_set_version_id)
        self.assertEqual([item["case_version_id"] for item in membership], [created.eval_case_version_id])
        self.assertEqual(len(artifact_count), 2)

    def test_eval_case_version_replaces_current_case_in_new_eval_set_without_mutating_old_snapshot(self):
        skill = self.create_skill()
        first = self.repository.create_eval_case(
            skill_id=skill.skill_id,
            title="PR: null nickname",
            input_text="old input",
            expected_output="old expectation",
            actor="tester",
        )
        second = self.repository.create_eval_case_version(
            case_id=first.eval_case_id,
            input_text="new input",
            expected_output="new expectation",
            actor="tester",
        )

        with self.engine.connect() as connection:
            old_membership = connection.execute(
                select(eval_set_case_versions.c.case_version_id).where(
                    eval_set_case_versions.c.eval_set_version_id == first.eval_set_version_id
                )
            ).scalars().all()
            new_membership = connection.execute(
                select(eval_set_case_versions.c.case_version_id).where(
                    eval_set_case_versions.c.eval_set_version_id == second.eval_set_version_id
                )
            ).scalars().all()
            eval_case = connection.execute(select(eval_cases).where(eval_cases.c.id == first.eval_case_id)).mappings().one()
            latest_eval_set_version = connection.execute(
                select(eval_set_versions).where(eval_set_versions.c.id == second.eval_set_version_id)
            ).mappings().one()

        self.assertEqual(old_membership, [first.eval_case_version_id])
        self.assertEqual(new_membership, [second.eval_case_version_id])
        self.assertEqual(eval_case["current_version_id"], second.eval_case_version_id)
        self.assertEqual(latest_eval_set_version["version_number"], 3)

    def test_eval_case_version_can_be_created_without_moving_case_or_eval_set_current_pointer(self):
        skill = self.create_skill()
        first = self.repository.create_eval_case(
            skill_id=skill.skill_id,
            title="PR: token leak",
            input_text="old input",
            expected_output="old expectation",
            actor="tester",
        )
        candidate = self.repository.create_eval_case_version(
            case_id=first.eval_case_id,
            input_text="candidate input",
            expected_output="candidate expectation",
            actor="tester",
            make_current=False,
        )

        with self.engine.connect() as connection:
            eval_case = connection.execute(select(eval_cases).where(eval_cases.c.id == first.eval_case_id)).mappings().one()
            eval_set = connection.execute(select(eval_sets).where(eval_sets.c.id == skill.eval_set_id)).mappings().one()

        self.assertEqual(eval_case["current_version_id"], first.eval_case_version_id)
        self.assertEqual(eval_set["current_version_id"], first.eval_set_version_id)
        self.assertEqual(candidate.eval_set_version_id, first.eval_set_version_id)

    def test_create_eval_case_requires_existing_skill_eval_set(self):
        with self.assertRaisesRegex(NotFoundError, "Primary EvalSet not found"):
            self.repository.create_eval_case(
                skill_id="missing",
                title="Missing skill",
                input_text="input",
                expected_output="expected",
                actor="tester",
            )

    def create_skill(self, *, slug: str = "code-reviewer", digest: str = "digest-bundle"):
        return self.repository.create_skill(
            slug=slug,
            owner_ref="skillhub-lab",
            variant_name="Variant A",
            variant_label="Baseline",
            variant_summary="Baseline maintained answer.",
            tags=["codex"],
            content_ref=ContentRef(kind="skill_bundle", locator=f"memory:{slug}", digest=digest),
            change_summary="Initial version.",
            actor="tester",
        )


if __name__ == "__main__":
    unittest.main()
