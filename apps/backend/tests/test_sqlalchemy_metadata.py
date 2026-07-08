import unittest

from sqlalchemy import ForeignKeyConstraint, Index, UniqueConstraint

from skillhub.models.schema.tables import metadata
from tests.conftest import ensure_postgres_test_database


class SqlAlchemyMetadataTest(unittest.TestCase):
    def test_metadata_declares_all_schema_tables(self):
        self.assertEqual(
            set(metadata.tables),
            {
                "artifacts",
                "skills",
                "skill_versions",
                "eval_sets",
                "eval_cases",
                "eval_case_versions",
                "eval_set_cases",
                "eval_runs",
                "case_results",
                "eval_case_runs",
                "jobs",
                "worker_heartbeats",
                "saved_views",
                "skill_tags",
                "tag_groups",
                "tag_values",
                "groups",
                "group_memberships",
                "role_assignments",
                "accepted_verifications",
                "review_requests",
                "review_request_reviewers",
                "review_responses",
                "publish_targets",
                "review_request_publish_targets",
                "review_check_results",
                "publish_records",
                "opencode_agents",
                "skill_builder_sessions",
                "skill_builder_messages",
                "notifications",
                "audit_events",
            },
        )

    def test_metadata_can_create_postgresql_test_schema(self):
        from skillhub.views.dependencies import create_postgres_engine, resolve_database_url

        ensure_postgres_test_database()
        engine = create_postgres_engine(resolve_database_url())
        metadata.drop_all(engine)
        metadata.create_all(engine)
        with engine.connect() as connection:
            self.assertTrue(engine.dialect.has_table(connection, "skills"))
        metadata.drop_all(engine)
        engine.dispose()

    def test_eval_run_same_skill_composite_foreign_keys_are_mapped(self):
        self.assertNotIn("strategy", metadata.tables["eval_runs"].c)
        self.assert_foreign_key(
            "eval_runs",
            "eval_runs_skill_version_skill_fkey",
            ("skill_version_id", "skill_id"),
            "skill_versions",
            ("id", "skill_id"),
        )
        self.assert_foreign_key(
            "eval_runs",
            "eval_runs_eval_set_skill_fkey",
            ("eval_set_id", "skill_id"),
            "eval_sets",
            ("id", "skill_id"),
        )

    def test_case_results_are_scoped_by_run_and_case_skill(self):
        self.assert_foreign_key(
            "case_results",
            "case_results_run_skill_fkey",
            ("run_id", "skill_id"),
            "eval_runs",
            ("id", "skill_id"),
        )
        self.assert_foreign_key(
            "case_results",
            "case_results_case_skill_fkey",
            ("case_version_id", "skill_id"),
            "eval_case_versions",
            ("id", "skill_id"),
        )

    def test_eval_case_runs_bind_case_version_and_async_job(self):
        self.assertNotIn("strategy", metadata.tables["eval_case_runs"].c)
        self.assert_foreign_key(
            "eval_case_runs",
            "eval_case_runs_skill_version_skill_fkey",
            ("skill_version_id", "skill_id"),
            "skill_versions",
            ("id", "skill_id"),
        )
        self.assert_foreign_key(
            "eval_case_runs",
            "eval_case_runs_eval_set_skill_fkey",
            ("eval_set_id", "skill_id"),
            "eval_sets",
            ("id", "skill_id"),
        )
        self.assert_foreign_key(
            "eval_case_runs",
            "eval_case_runs_case_skill_fkey",
            ("case_version_id", "skill_id"),
            "eval_case_versions",
            ("id", "skill_id"),
        )

    def test_version_uniqueness_constraints_are_mapped(self):
        self.assert_unique_constraint("skill_versions", "skill_versions_skill_version_unique", ("skill_id", "version_number"))
        self.assert_unique_constraint("skill_versions", "skill_versions_skill_semver_unique", ("skill_id", "version"))
        self.assert_unique_constraint("eval_case_versions", "eval_case_versions_case_version_unique", ("case_id", "version_number"))

    def test_eval_case_version_workspace_steps_and_runner_config_are_mapped(self):
        table = metadata.tables["eval_case_versions"]

        self.assertIn("workspace_artifact_id", table.c)
        self.assertTrue(table.c.workspace_artifact_id.nullable)
        self.assertIn("steps", table.c)
        self.assertIn("runner_config", table.c)

    def test_opencode_runner_metadata_columns_are_mapped(self):
        self.assertIn("runner_metadata", metadata.tables["eval_case_runs"].c)
        self.assertIn("attempts", metadata.tables["jobs"].c)
        self.assertIn("locked_by", metadata.tables["jobs"].c)
        self.assertIn("last_heartbeat_at", metadata.tables["jobs"].c)
        heartbeat_columns = metadata.tables["worker_heartbeats"].c
        for column in [
            "worker_id",
            "status",
            "current_job_id",
            "current_job_type",
            "current_run_id",
            "current_session_id",
            "last_seen_at",
            "started_at",
            "metadata",
        ]:
            self.assertIn(column, heartbeat_columns)

    def test_query_indexes_are_mapped(self):
        for table_name, index_name in [
            ("skill_versions", "skill_versions_skill_id_idx"),
            ("eval_case_versions", "eval_case_versions_case_id_idx"),
            ("eval_set_cases", "eval_set_cases_case_id_idx"),
            ("eval_runs", "eval_runs_skill_version_id_idx"),
            ("eval_runs", "eval_runs_eval_set_id_idx"),
            ("eval_runs", "eval_runs_context_hash_idx"),
            ("case_results", "case_results_case_version_id_idx"),
            ("eval_case_runs", "eval_case_runs_case_version_id_idx"),
            ("eval_case_runs", "eval_case_runs_job_id_idx"),
            ("accepted_verifications", "accepted_verifications_context_idx"),
            ("review_requests", "review_requests_skill_version_idx"),
            ("review_request_reviewers", "review_request_reviewers_actor_idx"),
            ("review_responses", "review_responses_reviewer_idx"),
            ("review_request_publish_targets", "review_request_publish_targets_target_idx"),
            ("review_check_results", "review_check_results_check_idx"),
            ("publish_targets", "publish_targets_enabled_idx"),
            ("publish_records", "publish_records_skill_version_idx"),
            ("publish_records", "publish_records_target_status_idx"),
            ("notifications", "notifications_recipient_idx"),
            ("skill_builder_sessions", "skill_builder_sessions_actor_idx"),
            ("skill_builder_messages", "skill_builder_messages_session_idx"),
            ("saved_views", "saved_views_skill_type_idx"),
            ("skill_tags", "skill_tags_group_value_idx"),
            ("tag_groups", "tag_groups_sort_idx"),
            ("tag_values", "tag_values_group_sort_idx"),
            ("group_memberships", "group_memberships_subject_idx"),
            ("jobs", "jobs_status_created_at_idx"),
            ("worker_heartbeats", "worker_heartbeats_last_seen_idx"),
            ("role_assignments", "role_assignments_subject_idx"),
        ]:
            self.assertIn(index_name, self.index_names(table_name))

    def test_skills_link_to_current_skill_version(self):
        self.assert_foreign_key(
            "skills",
            "skills_current_version_fkey",
            ("current_version_id", "id"),
            "skill_versions",
            ("id", "skill_id"),
        )

    def test_accepted_verifications_link_to_exact_run_pointer(self):
        self.assert_unique_constraint(
            "accepted_verifications",
            "accepted_verifications_context_unique",
            ("skill_id", "skill_version_id", "eval_set_id", "run_context_hash"),
        )
        self.assert_foreign_key(
            "accepted_verifications",
            "accepted_verifications_skill_version_skill_fkey",
            ("skill_version_id", "skill_id"),
            "skill_versions",
            ("id", "skill_id"),
        )
        self.assert_foreign_key(
            "accepted_verifications",
            "accepted_verifications_eval_set_skill_fkey",
            ("eval_set_id", "skill_id"),
            "eval_sets",
            ("id", "skill_id"),
        )
        self.assert_foreign_key(
            "accepted_verifications",
            "accepted_verifications_eval_run_skill_fkey",
            ("eval_run_id", "skill_id"),
            "eval_runs",
            ("id", "skill_id"),
        )

    def assert_foreign_key(
        self,
        table_name: str,
        constraint_name: str,
        local_columns: tuple[str, ...],
        referred_table: str,
        referred_columns: tuple[str, ...],
    ) -> None:
        table = metadata.tables[table_name]
        constraints = [item for item in table.constraints if isinstance(item, ForeignKeyConstraint)]
        match = next((item for item in constraints if item.name == constraint_name), None)
        self.assertIsNotNone(match, constraint_name)
        assert match is not None
        self.assertEqual(tuple(column.name for column in match.columns), local_columns)
        self.assertEqual(match.referred_table.name, referred_table)
        self.assertEqual(tuple(element.column.name for element in match.elements), referred_columns)

    def assert_unique_constraint(self, table_name: str, constraint_name: str, columns: tuple[str, ...]) -> None:
        table = metadata.tables[table_name]
        constraints = [item for item in table.constraints if isinstance(item, UniqueConstraint)]
        match = next((item for item in constraints if item.name == constraint_name), None)
        self.assertIsNotNone(match, constraint_name)
        assert match is not None
        self.assertEqual(tuple(column.name for column in match.columns), columns)

    def index_names(self, table_name: str) -> set[str]:
        return {item.name for item in metadata.tables[table_name].indexes if isinstance(item, Index)}


if __name__ == "__main__":
    unittest.main()
