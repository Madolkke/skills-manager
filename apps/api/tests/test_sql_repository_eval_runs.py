from sqlalchemy import select

from skillhub.domain.errors import FieldInvariantError, InvariantError
from skillhub.domain.models import ContentRef
from skillhub.infrastructure.db.tables import accepted_verifications, artifacts, case_results, eval_runs

from tests.repository_test_case import SqlRepositoryTestCase


class SqlRepositoryEvalRunTest(SqlRepositoryTestCase):
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
