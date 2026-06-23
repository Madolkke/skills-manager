from tests.api_command_test_case import ApiCommandTestCase


class ApiEvalFlowTest(ApiCommandTestCase):
    def test_command_flow_records_eval_run_with_context_and_actual_output(self):
        skill = self.create_skill("command-flow")
        case = self.create_eval_case(skill["skill_id"])

        queued = self.enqueue_case_run(
            skill["skill_version_id"],
            case["eval_set_id"],
            case["eval_case_version_id"],
            environment_tags=["windows", "codex", "windows"],
            run_context={"os": "windows", "shell": "git-bash", "model": "gpt-5"},
        )
        self.assertNotIn("strategy", queued)
        self.repository.finalize_eval_case_run(
            eval_case_run_id=queued["eval_case_run_id"],
            passed=False,
            actual_output="The run missed the ownerId finding.",
            actor="tester",
        )
        run = self.client.post(
            "/api/eval-runs/aggregations",
            json={
                "skill_version_id": skill["skill_version_id"],
                "eval_set_id": case["eval_set_id"],
                "environment_tags": ["windows", "codex", "windows"],
                "run_context": {"os": "windows", "shell": "git-bash", "model": "gpt-5"},
            },
        )

        self.assertEqual(run.status_code, 200)
        payload = run.json()
        self.assertEqual(payload["skill_version_id"], skill["skill_version_id"])
        self.assertEqual(payload["environment_tags"], ["codex", "windows"])
        self.assertEqual(payload["run_context"]["os"], "windows")

        detail = self.client.get(f"/api/eval-runs/{payload['eval_run_id']}").json()
        self.assertEqual(detail["skill_version"]["id"], skill["skill_version_id"])
        self.assertEqual(detail["eval_run"]["environment_tags"], ["codex", "windows"])
        self.assertEqual(detail["case_results"][0]["result_artifact"]["content_text"], "The run missed the ownerId finding.")
        self.assertEqual(
            detail["case_results"][0]["case_version"]["steps"][0]["assertions"][0]["assertion_params"]["text"],
            "Flag missing ownerId filter.",
        )

        history = self.client.get(f"/api/skills/{skill['skill_id']}/eval-runs").json()
        self.assertEqual(history["runs"][0]["eval_run"]["id"], payload["eval_run_id"])
        self.assertEqual(history["runs"][0]["skill_version"]["id"], skill["skill_version_id"])
        self.assertNotIn("strategy", detail["eval_run"])

    def test_removed_manual_eval_run_endpoint_returns_not_found(self):
        response = self.client.post("/api/eval-runs", json={})

        self.assertEqual(response.status_code, 404)

    def test_eval_run_history_and_matrix_filter_by_skill_version(self):
        skill = self.create_skill("history-filter")
        case = self.create_eval_case(skill["skill_id"])
        candidate = self.create_skill_version(skill["skill_id"], "history-filter-v2")
        self.record_run(skill["skill_version_id"], case["eval_set_id"], case["eval_case_version_id"], False)
        candidate_run = self.record_run(candidate["skill_version_id"], case["eval_set_id"], case["eval_case_version_id"], True)

        history = self.client.get(
            f"/api/skills/{skill['skill_id']}/eval-runs",
            params={"skill_version_id": candidate["skill_version_id"]},
        ).json()
        matrix = self.client.get(
            f"/api/skills/{skill['skill_id']}/eval-run-matrix",
            params={"skill_version_id": candidate["skill_version_id"]},
        ).json()

        self.assertEqual([row["eval_run"]["id"] for row in history["runs"]], [candidate_run["eval_run_id"]])
        self.assertEqual(matrix["runs"][0]["skill_version"]["id"], candidate["skill_version_id"])
        self.assertEqual(matrix["cells"][0]["passed"], True)

    def test_eval_run_compare_endpoint_returns_case_impact(self):
        skill = self.create_skill("compare-flow")
        case = self.create_eval_case(skill["skill_id"])
        candidate = self.create_skill_version(skill["skill_id"], "compare-flow-v2")
        baseline = self.record_run(skill["skill_version_id"], case["eval_set_id"], case["eval_case_version_id"], False)
        candidate_run = self.record_run(candidate["skill_version_id"], case["eval_set_id"], case["eval_case_version_id"], True)

        response = self.client.get(
            "/api/eval-runs/compare",
            params={"baseline_run_id": baseline["eval_run_id"], "candidate_run_id": candidate_run["eval_run_id"]},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["candidate"]["skill_version"]["id"], candidate["skill_version_id"])
        self.assertEqual(response.json()["summary"]["fixed"], 1)

    def test_accepted_verification_requires_maintainer_or_owner_and_scopes_run_context(self):
        skill = self.create_skill("accepted-context")
        case = self.create_eval_case(skill["skill_id"])
        linux_run = self.record_run(
            skill["skill_version_id"],
            case["eval_set_id"],
            case["eval_case_version_id"],
            True,
            environment_tags=["linux"],
            run_context={"os": "linux"},
        )
        windows_run = self.record_run(
            skill["skill_version_id"],
            case["eval_set_id"],
            case["eval_case_version_id"],
            True,
            environment_tags=["windows"],
            run_context={"os": "windows"},
        )

        viewer = self.client.post(
            "/api/eval-runs/accepted-verifications",
            headers={"X-SkillHub-Actor": "readonly-user"},
            json={"eval_run_id": linux_run["eval_run_id"], "note": "No permission."},
        )
        linux_acceptance = self.client.post(
            "/api/eval-runs/accepted-verifications",
            json={"eval_run_id": linux_run["eval_run_id"], "note": "Accepted on Linux."},
        )
        windows_acceptance = self.client.post(
            "/api/eval-runs/accepted-verifications",
            json={"eval_run_id": windows_run["eval_run_id"], "note": "Accepted on Windows."},
        )

        self.assertEqual(viewer.status_code, 403)
        self.assertEqual(linux_acceptance.status_code, 200)
        self.assertEqual(windows_acceptance.status_code, 200)
        self.assertNotEqual(
            linux_acceptance.json()["accepted_verification"]["id"],
            windows_acceptance.json()["accepted_verification"]["id"],
        )

    def test_aggregate_eval_run_requires_finished_case_runs(self):
        skill = self.create_skill("run-validation")
        case = self.create_eval_case(skill["skill_id"])

        response = self.client.post(
            "/api/eval-runs/aggregations",
            json={
                "skill_version_id": skill["skill_version_id"],
                "eval_set_id": case["eval_set_id"],
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["field_errors"][0]["field"], f"case_runs.{case['eval_case_version_id']}")

    def test_aggregate_eval_run_rejects_empty_eval_set(self):
        skill = self.create_skill("empty-run-validation")
        empty_set = self.client.post(
            f"/api/skills/{skill['skill_id']}/eval-sets",
            json={"name": "Empty"},
        ).json()

        response = self.client.post(
            "/api/eval-runs/aggregations",
            json={
                "skill_version_id": skill["skill_version_id"],
                "eval_set_id": empty_set["id"],
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["field_errors"][0]["field"], "eval_set_id")
        self.assertEqual(response.json()["field_errors"][0]["code"], "eval_run.eval_set_empty")
