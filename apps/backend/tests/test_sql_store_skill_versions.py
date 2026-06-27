from sqlalchemy import select

from skillhub.models.errors import NotFoundError
from skillhub.models.entities import ContentRef
from skillhub.models.schema.tables import eval_sets, skill_versions, skills

from tests.store_test_case import SqlStoreTestCase


class SqlStoreSkillVersionTest(SqlStoreTestCase):
    def test_create_skill_writes_current_skill_version_and_primary_eval_set(self):
        result = self.store.create_skill(
            slug="code-reviewer",
            owner_ref="skillhub-lab",
            content_ref=ContentRef(kind="skill_bundle", locator="memory:bundle", digest="digest-bundle"),
            change_summary="Initial version.",
            actor="tester",
        )

        with self.engine.connect() as connection:
            skill = connection.execute(select(skills).where(skills.c.id == result.skill_id)).mappings().one()
            version = connection.execute(
                select(skill_versions).where(skill_versions.c.id == result.skill_version_id)
            ).mappings().one()
            eval_set = connection.execute(select(eval_sets).where(eval_sets.c.id == result.eval_set_id)).mappings().one()

        self.assertEqual(skill["current_version_id"], result.skill_version_id)
        self.assertEqual(version["skill_id"], result.skill_id)
        self.assertEqual(version["version_number"], 1)
        self.assertEqual(version["version"], "0.0.1")
        self.assertEqual(result.version, "0.0.1")
        self.assertEqual(version["content_ref"]["kind"], "skill_bundle")
        self.assertEqual(eval_set["skill_id"], result.skill_id)
        self.assertEqual(eval_set["name"], "Primary")

    def test_candidate_skill_version_does_not_move_current_pointer(self):
        skill = self.create_skill()

        candidate = self.store.create_skill_version(
            skill_id=skill.skill_id,
            content_ref=ContentRef(kind="skill_bundle", locator="memory:candidate", digest="digest-candidate"),
            change_summary="Candidate version.",
            actor="tester",
            make_current=False,
        )

        with self.engine.connect() as connection:
            skill_row = connection.execute(select(skills).where(skills.c.id == skill.skill_id)).mappings().one()
            version = connection.execute(
                select(skill_versions).where(skill_versions.c.id == candidate.skill_version_id)
            ).mappings().one()

        self.assertEqual(candidate.version_number, 2)
        self.assertEqual(candidate.version, "0.0.2")
        self.assertEqual(skill_row["current_version_id"], skill.skill_version_id)
        self.assertEqual(version["change_summary"], "Candidate version.")

    def test_explicit_semver_is_saved_for_skill_version(self):
        skill = self.create_skill()

        created = self.store.create_skill_version(
            skill_id=skill.skill_id,
            content_ref=ContentRef(kind="skill_bundle", locator="memory:v2", digest="digest-v2"),
            change_summary="Major release.",
            actor="tester",
            make_current=False,
            version="2.0.0",
        )

        with self.engine.connect() as connection:
            version = connection.execute(
                select(skill_versions).where(skill_versions.c.id == created.skill_version_id)
            ).mappings().one()

        self.assertEqual(created.version, "2.0.0")
        self.assertEqual(version["version"], "2.0.0")

    def test_explicit_semver_is_saved_for_initial_skill_version(self):
        result = self.store.create_skill(
            slug="initial-semver",
            owner_ref="skillhub-lab",
            content_ref=ContentRef(kind="skill_bundle", locator="memory:initial-semver", digest="digest-initial-semver"),
            change_summary="Initial preview.",
            actor="tester",
            version="0.1.0",
        )

        with self.engine.connect() as connection:
            version = connection.execute(
                select(skill_versions).where(skill_versions.c.id == result.skill_version_id)
            ).mappings().one()

        self.assertEqual(result.version, "0.1.0")
        self.assertEqual(version["version"], "0.1.0")

    def test_duplicate_semver_is_rejected_per_skill(self):
        skill = self.create_skill()

        with self.assertRaisesRegex(Exception, "SkillVersion version already exists"):
            self.store.create_skill_version(
                skill_id=skill.skill_id,
                content_ref=ContentRef(kind="skill_bundle", locator="memory:duplicate", digest="digest-duplicate"),
                change_summary="Duplicate version.",
                actor="tester",
                make_current=False,
                version="0.0.1",
            )

    def test_make_current_skill_version_moves_current_pointer(self):
        skill = self.create_skill()

        created = self.store.create_skill_version(
            skill_id=skill.skill_id,
            content_ref=ContentRef(kind="skill_bundle", locator="memory:v2", digest="digest-v2"),
            change_summary="Make current.",
            actor="tester",
            make_current=True,
        )

        with self.engine.connect() as connection:
            skill_row = connection.execute(select(skills).where(skills.c.id == skill.skill_id)).mappings().one()

        self.assertEqual(skill_row["current_version_id"], created.skill_version_id)

    def test_create_skill_version_requires_existing_skill(self):
        with self.assertRaisesRegex(NotFoundError, "Skill not found"):
            self.store.create_skill_version(
                skill_id="missing",
                content_ref=ContentRef(kind="skill_bundle", locator="memory:v2", digest="digest-v2"),
                change_summary="Missing skill.",
                actor="tester",
                make_current=False,
            )
