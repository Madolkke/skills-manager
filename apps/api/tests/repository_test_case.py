import json

from skillhub.domain.models import ContentRef, digest_text
from skillhub.infrastructure.db.repositories import SqlSkillRepository
from tests.postgres_test_case import PostgresTestCase


class SqlRepositoryTestCase(PostgresTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.repository = SqlSkillRepository(self.engine)

    def create_skill(self, slug: str = "code-reviewer", digest: str = "digest-code"):
        return self.repository.create_skill(
            slug=slug,
            owner_ref="skillhub-lab",
            content_ref=ContentRef(kind="skill_bundle", locator=f"memory:{slug}", digest=digest),
            change_summary="Initial version.",
            actor="tester",
        )

    def bundle_content_ref(self, slug: str, guidance: str) -> ContentRef:
        manifest = {
            "entry_path": f"{slug}/SKILL.md",
            "files": [
                {
                    "path": f"{slug}/SKILL.md",
                    "content_text": f"---\nname: {slug}\ndescription: Reviewer.\n---\n{guidance}\n",
                    "sha256": digest_text(guidance),
                    "size_bytes": len(guidance),
                    "binary": False,
                }
            ],
        }
        artifact = self.repository.create_text_artifact(
            kind="skill_bundle",
            namespace=f"test:{slug}",
            content=json.dumps(manifest, sort_keys=True),
            actor="tester",
        )
        return ContentRef(
            kind="artifact",
            locator=f"artifact:{artifact['id']}",
            digest=artifact["digest"],
            path=f"{slug}/SKILL.md",
        )
