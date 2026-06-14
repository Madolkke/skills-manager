from sqlalchemy import select

from skillhub.domain.errors import NotFoundError
from skillhub.domain.models import ContentRef
from skillhub.infrastructure.db.tables import eval_sets, skill_versions, skills

from tests.repository_test_case import SqlRepositoryTestCase


class SqlRepositorySkillVersionTest(SqlRepositoryTestCase):
    def test_create_skill_writes_current_skill_version_and_primary_eval_set(self):
        result = self.repository.create_skill(
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
        self.assertEqual(version["content_ref"]["kind"], "skill_bundle")
        self.assertEqual(eval_set["skill_id"], result.skill_id)
        self.assertEqual(eval_set["name"], "Primary")

    def test_candidate_skill_version_does_not_move_current_pointer(self):
        skill = self.create_skill()

        candidate = self.repository.create_skill_version(
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
        self.assertEqual(skill_row["current_version_id"], skill.skill_version_id)
        self.assertEqual(version["change_summary"], "Candidate version.")

    def test_make_current_skill_version_moves_current_pointer(self):
        skill = self.create_skill()

        created = self.repository.create_skill_version(
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
            self.repository.create_skill_version(
                skill_id="missing",
                content_ref=ContentRef(kind="skill_bundle", locator="memory:v2", digest="digest-v2"),
                change_summary="Missing skill.",
                actor="tester",
                make_current=False,
            )
