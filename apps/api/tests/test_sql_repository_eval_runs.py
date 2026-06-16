from sqlalchemy import select
import base64

from skillhub.domain.errors import FieldInvariantError, InvariantError
from skillhub.domain.models import ContentRef
from skillhub.infrastructure.db.tables import accepted_verifications, artifacts, case_results, eval_case_runs, eval_runs, jobs

from tests.repository_test_case import SqlRepositoryTestCase


class SqlRepositoryEvalRunTest(SqlRepositoryTestCase):
    def test_create_eval_case_can_attach_zip_artifact(self):
        skill = self.create_skill()
        zip_bytes = b"PK\x03\x04case archive"

        created = self.repository.create_eval_case(
            skill_id=skill.skill_id,
            title="Archive context",
            input_text="Review the attached archive.",
            expected_output="Flag missing test coverage.",
            actor="tester",
            attachment_name="context.zip",
            attachment_base64=base64.b64encode(zip_bytes).decode("ascii"),
        )

        with self.engine.connect() as connection:
            artifact = connection.execute(
                select(artifacts).where(artifacts.c.id == created.attachment_artifact_id)
            ).mappings().one()
            case_version = self.repository._case_version_detail(
                connection,
                self.repository._eval_case_version_row(connection, created.eval_case_version_id),
            )

        self.assertEqual(artifact["kind"], "eval_case_attachment")
        self.assertEqual(artifact["media_type"], "application/zip")
        self.assertEqual(artifact["size_bytes"], len(zip_bytes))
        self.assertEqual(case_version["attachment_artifact"]["id"], created.attachment_artifact_id)

    def test_aggregate_eval_run_persists_environment_context_and_actual_output_artifacts(self):
        skill = self.create_skill()
        case = self.repository.create_eval_case(
            skill_id=skill.skill_id,
            title="PR: missing owner check",
            input_text="Project.findMany()",
            expected_output="Flag missing ownerId filter.",
            actor="tester",
        )

        run = self.record_finished_eval_run(
            skill_version_id=skill.skill_version_id,
            eval_set_id=case.eval_set_id,
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

    def test_case_run_completion_is_aggregated_into_eval_run_snapshot(self):
        skill = self.create_skill()
        case = self.repository.create_eval_case(
            skill_id=skill.skill_id,
            title="Token logging",
            input_text="console.log(token)",
            expected_output="Flag token logging.",
            actor="tester",
        )

        queued = self.repository.enqueue_eval_case_run(
            skill_version_id=skill.skill_version_id,
            eval_set_id=case.eval_set_id,
            case_version_id=case.eval_case_version_id,
            actor="tester",
            environment_tags=["linux"],
            run_context={"os": "linux"},
        )
        finished = self.repository.finalize_eval_case_run(
            eval_case_run_id=queued.eval_case_run_id,
            passed=True,
            actual_output="Flagged token logging.",
            actor="tester",
        )
        run = self.repository.aggregate_eval_run(
            skill_version_id=skill.skill_version_id,
            eval_set_id=case.eval_set_id,
            actor="tester",
            environment_tags=["linux"],
            run_context={"os": "linux"},
        )

        with self.engine.connect() as connection:
            case_run = connection.execute(select(eval_case_runs).where(eval_case_runs.c.id == finished.eval_case_run_id)).mappings().one()
            job = connection.execute(select(jobs).where(jobs.c.id == finished.job_id)).mappings().one()
            result = connection.execute(select(case_results).where(case_results.c.run_id == run.eval_run_id)).mappings().one()

        self.assertEqual(case_run["skill_version_id"], skill.skill_version_id)
        self.assertEqual(case_run["case_version_id"], case.eval_case_version_id)
        self.assertEqual(case_run["status"], "succeeded")
        self.assertEqual(job["status"], "succeeded")
        self.assertEqual(result["passed"], True)
        self.assertEqual(run.passed, 1)

        latest = self.repository.latest_eval_case_run_details(
            skill_version_id=skill.skill_version_id,
            eval_set_id=case.eval_set_id,
            environment_tags=["linux"],
            run_context={"os": "linux"},
        )
        self.assertEqual(latest[0]["eval_case_run"]["id"], finished.eval_case_run_id)
        self.assertEqual(latest[0]["result_artifact"]["content_text"], "Flagged token logging.")

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
            self.repository.aggregate_eval_run(
                skill_version_id=first.skill_version_id,
                eval_set_id=case.eval_set_id,
                actor="tester",
            )

    def test_eval_run_aggregation_requires_finished_case_runs(self):
        skill = self.create_skill()
        case = self.repository.create_eval_case(
            skill_id=skill.skill_id,
            title="PR: missing owner check",
            input_text="Project.findMany()",
            expected_output="Flag missing ownerId filter.",
            actor="tester",
        )

        with self.assertRaises(FieldInvariantError) as error:
            self.repository.aggregate_eval_run(
                skill_version_id=skill.skill_version_id,
                eval_set_id=case.eval_set_id,
                actor="tester",
            )

        self.assertEqual(error.exception.field_errors[0].field, f"case_runs.{case.eval_case_version_id}")

    def test_eval_run_detail_returns_case_level_results_and_skill_version(self):
        skill = self.create_skill()
        case = self.repository.create_eval_case(
            skill_id=skill.skill_id,
            title="Token logging",
            input_text="console.log(token)",
            expected_output="Flag token logging.",
            actor="tester",
        )
        second_case = self.repository.create_eval_case(
            skill_id=skill.skill_id,
            title="Tenant scope",
            input_text="Project.all()",
            expected_output="Flag missing tenant scope.",
            actor="tester",
        )
        run = self.record_finished_eval_run(
            skill_version_id=skill.skill_version_id,
            eval_set_id=second_case.eval_set_id,
            results={
                case.eval_case_version_id: {"passed": True, "actual_output": "Flagged token logging."},
                second_case.eval_case_version_id: {"passed": False, "actual_output": "No tenant finding."},
            },
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
        self.assertEqual([item["position"] for item in detail.case_results], [0, 1])
        self.assertEqual([item["case"]["title"] for item in detail.case_results], ["Token logging", "Tenant scope"])

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
        self.record_finished_eval_run(
            skill_version_id=skill.skill_version_id,
            eval_set_id=case.eval_set_id,
            results={case.eval_case_version_id: False},
            actor="tester",
            environment_tags=["linux"],
            run_context={"os": "linux"},
        )
        candidate_run = self.record_finished_eval_run(
            skill_version_id=candidate.skill_version_id,
            eval_set_id=case.eval_set_id,
            results={case.eval_case_version_id: True},
            actor="tester",
            environment_tags=["windows"],
            run_context={"os": "windows"},
        )

        history = self.repository.list_eval_runs_for_skill(
            skill_id=skill.skill_id,
            skill_version_id=candidate.skill_version_id,
            eval_set_id=case.eval_set_id,
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
        linux_run = self.record_finished_eval_run(
            skill_version_id=skill.skill_version_id,
            eval_set_id=case.eval_set_id,
            results={case.eval_case_version_id: True},
            actor="tester",
            environment_tags=["linux"],
            run_context={"os": "linux"},
        )
        windows_run = self.record_finished_eval_run(
            skill_version_id=skill.skill_version_id,
            eval_set_id=case.eval_set_id,
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
        baseline = self.record_finished_eval_run(
            skill_version_id=skill.skill_version_id,
            eval_set_id=case.eval_set_id,
            results={case.eval_case_version_id: False},
            actor="tester",
            environment_tags=["linux"],
            run_context={"os": "linux"},
        )
        candidate_run = self.record_finished_eval_run(
            skill_version_id=candidate.skill_version_id,
            eval_set_id=case.eval_set_id,
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
