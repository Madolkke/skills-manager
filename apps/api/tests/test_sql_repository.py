import unittest

from sqlalchemy import create_engine, event, select

from skillhub.domain.errors import FieldInvariantError, InvariantError, NotFoundError
from skillhub.domain.models import ContentRef, digest_text
from skillhub.infrastructure.db.repositories import SqlSkillRepository
from skillhub.infrastructure.db.tables import (
    accepted_verifications,
    artifacts,
    audit_events,
    case_results,
    eval_runs,
    eval_set_versions,
    eval_sets,
    metadata,
    skill_versions,
    skills,
)


class SqlSkillRepositoryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        event.listen(self.engine, "connect", self.enable_sqlite_foreign_keys)
        metadata.create_all(self.engine)
        self.repository = SqlSkillRepository(self.engine)

    def enable_sqlite_foreign_keys(self, dbapi_connection, _connection_record) -> None:
        dbapi_connection.execute("pragma foreign_keys=on")

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
            eval_set_version = connection.execute(
                select(eval_set_versions).where(eval_set_versions.c.id == result.eval_set_version_id)
            ).mappings().one()

        self.assertEqual(skill["current_version_id"], result.skill_version_id)
        self.assertEqual(version["skill_id"], result.skill_id)
        self.assertEqual(version["version_number"], 1)
        self.assertEqual(version["content_ref"]["kind"], "skill_bundle")
        self.assertEqual(eval_set["current_version_id"], result.eval_set_version_id)
        self.assertEqual(eval_set_version["version_number"], 1)

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

    def test_record_eval_run_persists_environment_context_and_actual_output_artifacts(self):
        skill = self.create_skill()
        case = self.repository.create_eval_case(
            skill_id=skill.skill_id,
            title="PR: missing owner check",
            input_text="Project.findMany()",
            expected_output="Flag missing ownerId filter.",
            actor="tester",
        )

        run = self.repository.record_eval_run(
            skill_version_id=skill.skill_version_id,
            eval_set_version_id=case.eval_set_version_id,
            strategy="manual_pass_fail",
            results={
                case.eval_case_version_id: {
                    "passed": False,
                    "actual_output": "No finding returned.",
                }
            },
            actor="tester",
            environment_tags=["windows", "codex", "windows"],
            run_context={"os": "windows", "shell": "git-bash", "model": "gpt-5"},
        )

        with self.engine.connect() as connection:
            eval_run = connection.execute(select(eval_runs).where(eval_runs.c.id == run.eval_run_id)).mappings().one()
            result = connection.execute(
                select(case_results).where(case_results.c.run_id == run.eval_run_id)
            ).mappings().one()
            artifact = connection.execute(
                select(artifacts).where(artifacts.c.id == result["result_artifact_id"])
            ).mappings().one()

        self.assertEqual(run.skill_version_id, skill.skill_version_id)
        self.assertEqual(eval_run["environment_tags"], ["codex", "windows"])
        self.assertEqual(eval_run["run_context"], {"model": "gpt-5", "os": "windows", "shell": "git-bash"})
        self.assertEqual(eval_run["run_context_hash"], run.run_context_hash)
        self.assertEqual(artifact["kind"], "actual_output")
        self.assertEqual(artifact["content_text"], "No finding returned.")

    def test_eval_run_rejects_cross_skill_version_and_eval_set(self):
        first = self.create_skill(slug="code-reviewer", digest="digest-code")
        second = self.create_skill(slug="security-reviewer", digest="digest-security")
        case = self.repository.create_eval_case(
            skill_id=second.skill_id,
            title="Token logging",
            input_text="console.log(token)",
            expected_output="Flag token logging.",
            actor="tester",
        )

        with self.assertRaisesRegex(InvariantError, "same skill"):
            self.repository.record_eval_run(
                skill_version_id=first.skill_version_id,
                eval_set_version_id=case.eval_set_version_id,
                strategy="manual_pass_fail",
                results={case.eval_case_version_id: True},
                actor="tester",
            )

    def test_eval_run_results_must_match_eval_set_version(self):
        skill = self.create_skill()
        case = self.repository.create_eval_case(
            skill_id=skill.skill_id,
            title="PR: missing owner check",
            input_text="Project.findMany()",
            expected_output="Flag missing ownerId filter.",
            actor="tester",
        )

        with self.assertRaises(FieldInvariantError) as error:
            self.repository.record_eval_run(
                skill_version_id=skill.skill_version_id,
                eval_set_version_id=case.eval_set_version_id,
                strategy="manual_pass_fail",
                results={},
                actor="tester",
            )

        self.assertEqual(error.exception.field_errors[0].field, f"results.{case.eval_case_version_id}")

    def test_eval_run_detail_returns_case_level_results_and_skill_version(self):
        skill = self.create_skill()
        case = self.repository.create_eval_case(
            skill_id=skill.skill_id,
            title="Token logging",
            input_text="console.log(token)",
            expected_output="Flag token logging.",
            actor="tester",
        )
        run = self.repository.record_eval_run(
            skill_version_id=skill.skill_version_id,
            eval_set_version_id=case.eval_set_version_id,
            strategy="manual_pass_fail",
            results={case.eval_case_version_id: {"passed": True, "actual_output": "Flagged token logging."}},
            actor="tester",
            environment_tags=["linux"],
            run_context={"os": "linux"},
        )

        detail = self.repository.eval_run_detail(run.eval_run_id)

        self.assertEqual(detail.skill_version["id"], skill.skill_version_id)
        self.assertEqual(detail.eval_run["environment_tags"], ["linux"])
        self.assertEqual(detail.case_results[0]["result"]["passed"], True)
        self.assertEqual(detail.case_results[0]["result_artifact"]["content_text"], "Flagged token logging.")
        self.assertEqual(detail.case_results[0]["case_version"]["expected_output_artifact"]["content_text"], "Flag token logging.")

    def test_eval_run_history_filters_by_skill_version_and_context(self):
        skill = self.create_skill()
        candidate = self.repository.create_skill_version(
            skill_id=skill.skill_id,
            content_ref=ContentRef(kind="skill_bundle", locator="memory:v2", digest="digest-v2"),
            change_summary="Candidate version.",
            actor="tester",
            make_current=False,
        )
        case = self.repository.create_eval_case(
            skill_id=skill.skill_id,
            title="Tenant scope",
            input_text="Project.all()",
            expected_output="Flag missing tenant scope.",
            actor="tester",
        )
        self.repository.record_eval_run(
            skill_version_id=skill.skill_version_id,
            eval_set_version_id=case.eval_set_version_id,
            strategy="manual_pass_fail",
            results={case.eval_case_version_id: False},
            actor="tester",
            environment_tags=["linux"],
            run_context={"os": "linux"},
        )
        candidate_run = self.repository.record_eval_run(
            skill_version_id=candidate.skill_version_id,
            eval_set_version_id=case.eval_set_version_id,
            strategy="manual_pass_fail",
            results={case.eval_case_version_id: True},
            actor="tester",
            environment_tags=["windows"],
            run_context={"os": "windows"},
        )

        history = self.repository.list_eval_runs_for_skill(
            skill_id=skill.skill_id,
            skill_version_id=candidate.skill_version_id,
            eval_set_version_id=case.eval_set_version_id,
            strategy="manual_pass_fail",
            status="finished",
        )

        self.assertEqual([row["eval_run"]["id"] for row in history["runs"]], [candidate_run.eval_run_id])
        self.assertEqual(history["runs"][0]["skill_version"]["version_number"], 2)
        self.assertEqual(history["runs"][0]["eval_run"]["environment_tags"], ["windows"])

    def test_accept_eval_run_verification_is_scoped_by_run_context(self):
        skill = self.create_skill()
        case = self.repository.create_eval_case(
            skill_id=skill.skill_id,
            title="Tenant scope",
            input_text="Project.all()",
            expected_output="Flag missing tenant scope.",
            actor="tester",
        )
        linux_run = self.repository.record_eval_run(
            skill_version_id=skill.skill_version_id,
            eval_set_version_id=case.eval_set_version_id,
            strategy="manual_pass_fail",
            results={case.eval_case_version_id: True},
            actor="tester",
            environment_tags=["linux"],
            run_context={"os": "linux"},
        )
        windows_run = self.repository.record_eval_run(
            skill_version_id=skill.skill_version_id,
            eval_set_version_id=case.eval_set_version_id,
            strategy="manual_pass_fail",
            results={case.eval_case_version_id: True},
            actor="tester",
            environment_tags=["windows"],
            run_context={"os": "windows"},
        )

        linux_acceptance = self.repository.accept_eval_run_verification(
            eval_run_id=linux_run.eval_run_id,
            note="Accepted on Linux.",
            actor="tester",
        )
        windows_acceptance = self.repository.accept_eval_run_verification(
            eval_run_id=windows_run.eval_run_id,
            note="Accepted on Windows.",
            actor="tester",
        )

        with self.engine.connect() as connection:
            rows = connection.execute(select(accepted_verifications)).mappings().all()

        self.assertEqual(len(rows), 2)
        self.assertNotEqual(linux_acceptance["id"], windows_acceptance["id"])
        self.assertEqual({row["run_context_hash"] for row in rows}, {linux_run.run_context_hash, windows_run.run_context_hash})

    def test_compare_eval_runs_returns_skill_version_context(self):
        skill = self.create_skill()
        candidate = self.repository.create_skill_version(
            skill_id=skill.skill_id,
            content_ref=ContentRef(kind="skill_bundle", locator="memory:v2", digest="digest-v2"),
            change_summary="Candidate version.",
            actor="tester",
            make_current=False,
        )
        case = self.repository.create_eval_case(
            skill_id=skill.skill_id,
            title="Tenant scope",
            input_text="Project.all()",
            expected_output="Flag missing tenant scope.",
            actor="tester",
        )
        baseline = self.repository.record_eval_run(
            skill_version_id=skill.skill_version_id,
            eval_set_version_id=case.eval_set_version_id,
            strategy="manual_pass_fail",
            results={case.eval_case_version_id: False},
            actor="tester",
            environment_tags=["linux"],
            run_context={"os": "linux"},
        )
        candidate_run = self.repository.record_eval_run(
            skill_version_id=candidate.skill_version_id,
            eval_set_version_id=case.eval_set_version_id,
            strategy="manual_pass_fail",
            results={case.eval_case_version_id: True},
            actor="tester",
            environment_tags=["linux"],
            run_context={"os": "linux"},
        )

        comparison = self.repository.compare_eval_runs(
            baseline_run_id=baseline.eval_run_id,
            candidate_run_id=candidate_run.eval_run_id,
        )

        self.assertEqual(comparison["baseline"]["skill_version"]["id"], skill.skill_version_id)
        self.assertEqual(comparison["candidate"]["skill_version"]["id"], candidate.skill_version_id)
        self.assertEqual(comparison["summary"]["fixed"], 1)
        self.assertEqual(comparison["case_comparisons"][0]["change"], "fixed")

    def test_bundle_diff_uses_skill_version_ids(self):
        created = self.repository.create_skill(
            slug="bundle-reviewer",
            owner_ref="skillhub-lab",
            content_ref=self.bundle_content_ref("bundle-reviewer", "Flag auth regressions first."),
            change_summary="Initial bundle.",
            actor="tester",
        )
        second = self.repository.create_skill_version(
            skill_id=created.skill_id,
            content_ref=self.bundle_content_ref("bundle-reviewer", "Flag auth regressions and tenant leaks first."),
            change_summary="Add tenant guidance.",
            actor="tester",
            make_current=True,
        )

        diff = self.repository.bundle_diff(
            left_skill_version_id=created.skill_version_id,
            right_skill_version_id=second.skill_version_id,
        )

        self.assertEqual(diff["summary"]["changed"], 1)
        self.assertEqual(diff["left"]["skill_version_id"], created.skill_version_id)
        self.assertEqual(diff["right"]["skill_version_id"], second.skill_version_id)

    def test_skill_audit_events_include_skill_version_eval_run_and_verification_events(self):
        skill = self.create_skill()
        case = self.repository.create_eval_case(
            skill_id=skill.skill_id,
            title="Tenant scope",
            input_text="Project.all()",
            expected_output="Flag missing tenant scope.",
            actor="tester",
        )
        run = self.repository.record_eval_run(
            skill_version_id=skill.skill_version_id,
            eval_set_version_id=case.eval_set_version_id,
            strategy="manual_pass_fail",
            results={case.eval_case_version_id: True},
            actor="tester",
        )
        self.repository.accept_eval_run_verification(
            eval_run_id=run.eval_run_id,
            note="Accepted.",
            actor="tester",
        )

        events = self.repository.list_skill_audit_events(skill_id=skill.skill_id)

        self.assertIn("eval_run.accepted_verification_set", [event["action"] for event in events])
        with self.engine.connect() as connection:
            event_count = len(connection.execute(select(audit_events)).all())
        self.assertGreaterEqual(event_count, 2)

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
            content=__import__("json").dumps(manifest, sort_keys=True),
            actor="tester",
        )
        return ContentRef(
            kind="artifact",
            locator=f"artifact:{artifact['id']}",
            digest=artifact["digest"],
            path=f"{slug}/SKILL.md",
        )


if __name__ == "__main__":
    unittest.main()
