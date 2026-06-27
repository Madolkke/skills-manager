import json

from skillhub.models.entities import ContentRef, digest_text
from skillhub.models.store import SkillHubStore
from tests.postgres_test_case import PostgresTestCase


class SqlStoreTestCase(PostgresTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.store = SkillHubStore(self.engine)

    def create_skill(self, slug: str = "code-reviewer", digest: str = "digest-code"):
        return self.store.create_skill(
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
        artifact = self.store.create_text_artifact(
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

    def record_finished_eval_run(
        self,
        *,
        skill_version_id: str,
        eval_set_id: str,
        results: dict[str, bool | dict],
        actor: str = "tester",
        environment_tags: list[str] | None = None,
        run_context: dict | None = None,
    ):
        tags = environment_tags or []
        context = run_context or {}
        for case_version_id, value in results.items():
            result = value if isinstance(value, dict) else {"passed": bool(value)}
            queued = self.store.enqueue_eval_case_run(
                skill_version_id=skill_version_id,
                eval_set_id=eval_set_id,
                case_version_id=case_version_id,
                actor=actor,
                environment_tags=tags,
                run_context=context,
            )
            self.store.finalize_eval_case_run(
                eval_case_run_id=queued.eval_case_run_id,
                passed=bool(result["passed"]),
                actual_output=str(result.get("actual_output", "")),
                actor=actor,
            )
        return self.store.aggregate_eval_run(
            skill_version_id=skill_version_id,
            eval_set_id=eval_set_id,
            actor=actor,
            environment_tags=tags,
            run_context=context,
        )
