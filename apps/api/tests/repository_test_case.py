import json
import unittest

from sqlalchemy import create_engine, event

from skillhub.domain.models import ContentRef, digest_text
from skillhub.infrastructure.db.repositories import SqlSkillRepository
from skillhub.infrastructure.db.tables import metadata


class SqlRepositoryTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        event.listen(self.engine, "connect", self.enable_sqlite_foreign_keys)
        metadata.create_all(self.engine)
        self.repository = SqlSkillRepository(self.engine)

    def enable_sqlite_foreign_keys(self, dbapi_connection, _connection_record) -> None:
        dbapi_connection.execute("pragma foreign_keys=on")

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
