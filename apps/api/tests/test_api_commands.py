import unittest

from fastapi.testclient import TestClient

from skillhub.api.main import create_app, create_sqlite_engine


class ApiCommandTest(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_sqlite_engine("sqlite:///:memory:")
        self.client = TestClient(create_app(self.engine))

    def tearDown(self) -> None:
        self.engine.dispose()

    def test_command_flow_records_eval_run_with_context_and_actual_output(self):
        skill = self.create_skill("command-flow")
        case = self.create_eval_case(skill["skill_id"])

        run = self.client.post(
            "/api/eval-runs",
            json={
                "skill_version_id": skill["skill_version_id"],
                "eval_set_version_id": case["eval_set_version_id"],
                "environment_tags": ["windows", "codex", "windows"],
                "run_context": {"os": "windows", "shell": "git-bash", "model": "gpt-5"},
                "results": {
                    case["eval_case_version_id"]: {
                        "passed": False,
                        "actual_output": "The run missed the ownerId finding.",
                    }
                },
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
            detail["case_results"][0]["case_version"]["expected_output_artifact"]["content_text"],
            "Flag missing ownerId filter.",
        )

        history = self.client.get(f"/api/skills/{skill['skill_id']}/eval-runs").json()
        self.assertEqual(history["runs"][0]["eval_run"]["id"], payload["eval_run_id"])
        self.assertEqual(history["runs"][0]["skill_version"]["id"], skill["skill_version_id"])

    def test_old_variant_payloads_are_not_part_of_the_contract(self):
        skill = self.create_skill("no-variant-contract")
        case = self.create_eval_case(skill["skill_id"])

        response = self.client.post(
            "/api/eval-runs",
            json={
                "variant_version_id": skill["skill_version_id"],
                "eval_set_version_id": case["eval_set_version_id"],
                "results": {case["eval_case_version_id"]: True},
            },
        )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["field_errors"][0]["field"], "skill_version_id")
        self.assertEqual(self.client.post("/api/variants", json={}).status_code, 404)
        self.assertEqual(self.client.post("/api/variant-versions", json={}).status_code, 404)

    def test_skill_version_from_bundle_source_can_be_diffed(self):
        imported = self.import_standard_skill_bundle("bundle-diff")
        first_version_id = imported["skill_version_id"]
        second = self.client.post(
            "/api/skill-versions",
            json={
                "skill_id": imported["skill_id"],
                "source": self.bundle_source(
                    "bundle-diff",
                    skill_md_body="Flag auth regressions and tenant leaks first.",
                    checklist="Check owner filters, tenant filters, and secret logging.",
                ),
                "change_summary": "Add tenant guidance.",
                "make_current": True,
            },
        )
        self.assertEqual(second.status_code, 200)

        diff = self.client.get(
            "/api/artifacts/diff",
            params={
                "left_skill_version_id": first_version_id,
                "right_skill_version_id": second.json()["skill_version_id"],
            },
        )

        self.assertEqual(diff.status_code, 200)
        self.assertEqual(diff.json()["summary"]["changed"], 2)
        self.assertEqual(diff.json()["left"]["skill_version_id"], first_version_id)

    def test_bundle_diff_rejects_cross_skill_versions(self):
        first = self.import_standard_skill_bundle("first-diff")
        second = self.import_standard_skill_bundle("second-diff")

        response = self.client.get(
            "/api/artifacts/diff",
            params={
                "left_skill_version_id": first["skill_version_id"],
                "right_skill_version_id": second["skill_version_id"],
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("same skill", response.json()["detail"])

    def test_read_flow_returns_hub_skill_eval_set_and_version_details(self):
        skill = self.create_skill("read-flow")
        case = self.create_eval_case(skill["skill_id"])

        hub = self.client.get("/api/skills").json()
        detail = self.client.get(f"/api/skills/{skill['skill_id']}").json()
        eval_set = self.client.get(f"/api/eval-set-versions/{case['eval_set_version_id']}").json()

        self.assertEqual(hub[0]["summary"]["current_version"]["id"], skill["skill_version_id"])
        self.assertEqual(detail["summary"]["current_version"]["id"], skill["skill_version_id"])
        self.assertEqual(detail["versions"][0]["id"], skill["skill_version_id"])
        self.assertEqual(eval_set["cases"][0]["case_version"]["id"], case["eval_case_version_id"])

    def test_eval_run_history_and_matrix_filter_by_skill_version(self):
        skill = self.create_skill("history-filter")
        case = self.create_eval_case(skill["skill_id"])
        candidate = self.create_skill_version(skill["skill_id"], "history-filter-v2")
        self.record_run(skill["skill_version_id"], case["eval_set_version_id"], case["eval_case_version_id"], False)
        candidate_run = self.record_run(candidate["skill_version_id"], case["eval_set_version_id"], case["eval_case_version_id"], True)

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
        baseline = self.record_run(skill["skill_version_id"], case["eval_set_version_id"], case["eval_case_version_id"], False)
        candidate_run = self.record_run(candidate["skill_version_id"], case["eval_set_version_id"], case["eval_case_version_id"], True)

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
            case["eval_set_version_id"],
            case["eval_case_version_id"],
            True,
            environment_tags=["linux"],
            run_context={"os": "linux"},
        )
        windows_run = self.record_run(
            skill["skill_version_id"],
            case["eval_set_version_id"],
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

    def test_skill_capabilities_do_not_expose_variant_promote(self):
        skill = self.create_skill("capability-contract")

        response = self.client.get(f"/api/skills/{skill['skill_id']}/capabilities")

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("variant.promote", response.json()["permissions"])
        self.assertTrue(response.json()["permissions"]["verification.accept"])

    def test_saved_run_view_endpoints_create_list_and_delete_view(self):
        skill = self.create_skill("saved-view-api")

        created = self.client.post(
            "/api/saved-views",
            json={
                "skill_id": skill["skill_id"],
                "name": "Windows failures",
                "config": {"skill_version_id": skill["skill_version_id"], "status": "finished", "unknown": "ignored"},
            },
        )
        listed = self.client.get(f"/api/skills/{skill['skill_id']}/saved-views")
        deleted = self.client.delete(f"/api/saved-views/{created.json()['id']}")

        self.assertEqual(created.status_code, 200)
        self.assertEqual(created.json()["config"], {"skill_version_id": skill["skill_version_id"], "status": "finished"})
        self.assertEqual(len(listed.json()), 1)
        self.assertEqual(deleted.json(), {"ok": True})

    def test_update_skill_changes_identity_only(self):
        skill = self.create_skill("settings-api")

        response = self.client.patch(
            f"/api/skills/{skill['skill_id']}",
            json={"slug": "settings-api-v2", "owner_ref": "platform-team"},
        )
        detail = self.client.get(f"/api/skills/{skill['skill_id']}").json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["slug"], "settings-api-v2")
        self.assertEqual(detail["skill"]["owner_ref"], "platform-team")
        self.assertNotIn("default_variant_id", detail["skill"])

    def test_create_skill_duplicate_slug_returns_slug_field_error(self):
        self.create_skill("duplicate-skill")

        response = self.client.post("/api/skills", json=self.skill_payload("duplicate-skill"))

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["field_errors"][0]["field"], "slug")

    def test_create_skill_rejects_invalid_slug_format(self):
        response = self.client.post("/api/skills", json=self.skill_payload("Invalid Slug"))

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["field_errors"][0]["field"], "slug")

    def test_import_skill_from_file_tree_uses_skill_md_frontmatter(self):
        imported = self.import_standard_skill_bundle("imported-reviewer")
        detail = self.client.get(f"/api/skills/{imported['skill_id']}").json()

        self.assertEqual(imported["slug"], "imported-reviewer")
        self.assertEqual(imported["entry_path"], "SKILL.md")
        self.assertEqual(detail["summary"]["current_version"]["content_ref"]["kind"], "artifact")
        self.assertEqual(detail["summary"]["current_version"]["bundle_artifact"]["id"], imported["bundle_artifact_id"])
        self.assertEqual(len(detail["summary"]["current_version"]["bundle_files"]), 2)

    def test_request_actor_header_controls_created_owner(self):
        response = self.client.post(
            "/api/skills",
            headers={"X-SkillHub-Actor": "maintainer-one"},
            json=self.skill_payload("actor-owned-skill"),
        )
        assignments = self.client.get(f"/api/skills/{response.json()['skill_id']}/role-assignments").json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(assignments[0]["subject_id"], "maintainer-one")

    def test_eval_run_results_must_match_eval_set_version(self):
        skill = self.create_skill("run-validation")
        case = self.create_eval_case(skill["skill_id"])

        response = self.client.post(
            "/api/eval-runs",
            json={
                "skill_version_id": skill["skill_version_id"],
                "eval_set_version_id": case["eval_set_version_id"],
                "results": {},
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["field_errors"][0]["field"], f"results.{case['eval_case_version_id']}")

    def skill_payload(self, slug: str, digest: str | None = None):
        return {
            "slug": slug,
            "owner_ref": "skillhub-lab",
            "content_ref": {
                "kind": "skill_bundle",
                "locator": f"memory:{slug}",
                "digest": digest or f"digest-{slug}",
            },
            "change_summary": "Initial version.",
        }

    def create_skill(self, slug: str):
        response = self.client.post("/api/skills", json=self.skill_payload(slug))
        self.assertEqual(response.status_code, 200)
        return response.json()

    def create_skill_version(self, skill_id: str, slug: str):
        response = self.client.post(
            "/api/skill-versions",
            json={
                "skill_id": skill_id,
                "content_ref": {
                    "kind": "skill_bundle",
                    "locator": f"memory:{slug}",
                    "digest": f"digest-{slug}",
                },
                "change_summary": f"Create {slug}.",
                "make_current": False,
            },
        )
        self.assertEqual(response.status_code, 200)
        return response.json()

    def create_eval_case(self, skill_id: str):
        response = self.client.post(
            "/api/eval-cases",
            json={
                "skill_id": skill_id,
                "title": "PR: missing owner check",
                "input_text": "Project.findMany()",
                "expected_output": "Flag missing ownerId filter.",
            },
        )
        self.assertEqual(response.status_code, 200)
        return response.json()

    def record_run(
        self,
        skill_version_id: str,
        eval_set_version_id: str,
        case_version_id: str,
        passed: bool,
        environment_tags: list[str] | None = None,
        run_context: dict[str, str] | None = None,
    ):
        response = self.client.post(
            "/api/eval-runs",
            json={
                "skill_version_id": skill_version_id,
                "eval_set_version_id": eval_set_version_id,
                "environment_tags": environment_tags or [],
                "run_context": run_context or {},
                "results": {case_version_id: passed},
            },
        )
        self.assertEqual(response.status_code, 200)
        return response.json()

    def import_standard_skill_bundle(self, slug: str):
        response = self.client.post(
            "/api/skill-imports",
            json={
                "owner_ref": "skillhub-lab",
                "source": self.bundle_source(slug),
            },
        )
        self.assertEqual(response.status_code, 200)
        return response.json()

    def bundle_source(
        self,
        slug: str,
        skill_md_body: str = "Flag auth regressions first.",
        checklist: str = "Check owner filters and secret logging.",
    ):
        return {
            "kind": "files",
            "name": slug,
            "files": [
                {
                    "path": f"{slug}/SKILL.md",
                    "content_text": (
                        "---\n"
                        f"name: {slug}\n"
                        "description: Review pull requests for auth and data access regressions.\n"
                        "---\n"
                        "# Security Reviewing\n"
                        f"{skill_md_body}\n"
                    ),
                },
                {
                    "path": f"{slug}/references/checklist.md",
                    "content_text": f"{checklist}\n",
                },
            ],
        }


if __name__ == "__main__":
    unittest.main()
