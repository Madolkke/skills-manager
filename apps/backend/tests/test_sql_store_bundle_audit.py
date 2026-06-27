from sqlalchemy import select

from skillhub.models.schema.tables import audit_events

from tests.store_test_case import SqlStoreTestCase


class SqlStoreBundleAuditTest(SqlStoreTestCase):
    def test_bundle_diff_uses_skill_version_ids(self):
        created = self.store.create_skill(
            slug="bundle-reviewer",
            owner_ref="skillhub-lab",
            content_ref=self.bundle_content_ref("bundle-reviewer", "Flag auth regressions first."),
            change_summary="Initial bundle.",
            actor="tester",
        )
        second = self.store.create_skill_version(
            skill_id=created.skill_id,
            content_ref=self.bundle_content_ref("bundle-reviewer", "Flag auth regressions and tenant leaks first."),
            change_summary="Add tenant guidance.",
            actor="tester",
            make_current=True,
        )

        diff = self.store.bundle_diff(
            left_skill_version_id=created.skill_version_id,
            right_skill_version_id=second.skill_version_id,
        )

        self.assertEqual(diff["summary"]["changed"], 1)
        self.assertEqual(diff["left"]["skill_version_id"], created.skill_version_id)
        self.assertEqual(diff["right"]["skill_version_id"], second.skill_version_id)

    def test_skill_audit_events_include_skill_version_eval_run_and_verification_events(self):
        skill = self.create_skill()
        case = self.store.create_eval_case(
            skill_id=skill.skill_id,
            title="Tenant scope",
            input_text="Project.all()",
            expected_output="Flag missing tenant scope.",
            actor="tester",
        )
        run = self.record_finished_eval_run(
            skill_version_id=skill.skill_version_id,
            eval_set_id=case.eval_set_id,
            results={case.eval_case_version_id: True},
            actor="tester",
        )
        self.store.accept_eval_run_verification(
            eval_run_id=run.eval_run_id,
            note="Accepted.",
            actor="tester",
        )

        events = self.store.list_skill_audit_events(skill_id=skill.skill_id)

        self.assertIn("eval_run.accepted_verification_set", [event["action"] for event in events])
        with self.engine.connect() as connection:
            event_count = len(connection.execute(select(audit_events)).all())
        self.assertGreaterEqual(event_count, 2)
