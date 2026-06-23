from pathlib import Path
import re
import unittest


SCHEMA = Path(__file__).parents[1] / "skillhub" / "infrastructure" / "db" / "schema.sql"


class SchemaContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sql = SCHEMA.read_text(encoding="utf-8")
        cls.normalized = re.sub(r"\s+", " ", cls.sql.lower())

    def test_core_tables_exist(self):
        for table in [
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
            "accepted_verifications",
            "review_requests",
            "review_request_reviewers",
            "review_responses",
            "publish_targets",
            "review_request_publish_targets",
            "review_check_results",
            "publish_records",
            "notifications",
            "saved_views",
            "skill_tags",
            "tag_groups",
            "tag_values",
            "groups",
            "group_memberships",
            "jobs",
            "role_assignments",
            "audit_events",
        ]:
            self.assertIn(f"create table {table}", self.normalized)
        for removed_table in ["tag_sets", "variants", "variant_versions", "promotion_decisions"]:
            self.assertNotIn(f"create table {removed_table}", self.normalized)

    def test_run_same_skill_invariant_is_enforced_by_composite_foreign_keys(self):
        self.assertIn(
            "foreign key (skill_version_id, skill_id) references skill_versions(id, skill_id)",
            self.normalized,
        )
        self.assertIn(
            "foreign key (eval_set_id, skill_id) references eval_sets(id, skill_id)",
            self.normalized,
        )
        self.assertIn("constraint skill_versions_id_skill_unique unique (id, skill_id)", self.normalized)
        self.assertIn("constraint eval_sets_id_skill_unique unique (id, skill_id)", self.normalized)
        self.assertIn(
            "foreign key (current_version_id, id) references skill_versions(id, skill_id)",
            self.normalized,
        )

    def test_eval_set_membership_references_cases_not_case_versions(self):
        self.assertIn("create table eval_set_cases", self.normalized)
        self.assertIn(
            "foreign key (case_id, skill_id) references eval_cases(id, skill_id)",
            self.normalized,
        )
        table_sql = self._table_sql("eval_set_cases")
        self.assertIn("case_id text not null", table_sql)
        self.assertNotIn("case_version_id text not null", table_sql)

    def test_case_results_are_scoped_to_run_and_case_skill(self):
        self.assertIn("constraint eval_runs_id_skill_unique unique (id, skill_id)", self.normalized)
        self.assertIn("skill_id text not null", self._table_sql("case_results"))
        self.assertIn(
            "foreign key (run_id, skill_id) references eval_runs(id, skill_id)",
            self.normalized,
        )
        self.assertIn(
            "foreign key (case_version_id, skill_id) references eval_case_versions(id, skill_id)",
            self.normalized,
        )

    def test_eval_case_runs_bind_case_version_and_async_job(self):
        table_sql = self._table_sql("eval_case_runs")

        for snippet in [
            "job_id text references jobs(id)",
            "skill_version_id text not null",
            "eval_set_id text not null",
            "case_version_id text not null",
            "run_context_hash text not null",
            "passed boolean",
            "score integer",
        ]:
            self.assertIn(snippet, table_sql)
        self.assertIn(
            "foreign key (case_version_id, skill_id) references eval_case_versions(id, skill_id)",
            self.normalized,
        )
        self.assertNotIn("strategy", table_sql)

    def test_append_only_version_uniqueness_constraints_exist(self):
        for constraint in [
            "unique (owner_ref, slug)",
            "unique (skill_id, version_number)",
            "unique (skill_id, version)",
            "unique (case_id, version_number)",
            "primary key (run_id, case_version_id)",
        ]:
            self.assertIn(constraint, self.normalized)

    def test_skill_versions_have_optional_display_names(self):
        table_sql = self._table_sql("skill_versions")
        self.assertIn("version text not null", table_sql)
        self.assertIn("display_name text", table_sql)
        self.assertIn("skill_versions_version_semver_check", table_sql)

    def test_eval_case_versions_store_workspace_steps_and_runner_config(self):
        table_sql = self._table_sql("eval_case_versions")

        self.assertIn("workspace_artifact_id text references artifacts(id)", table_sql)
        self.assertIn("steps jsonb not null default '[]'::jsonb", table_sql)
        self.assertIn("runner_config jsonb not null default '{}'::jsonb", table_sql)
        self.assertIn("eval_case_versions_steps_array", table_sql)
        self.assertIn("eval_case_versions_runner_config_object", table_sql)

    def test_opencode_runner_fields_exist(self):
        self.assertIn("runner_metadata jsonb not null default '{}'::jsonb", self._table_sql("eval_case_runs"))
        jobs_sql = self._table_sql("jobs")
        self.assertIn("attempts integer not null default 0", jobs_sql)
        self.assertIn("locked_by text", jobs_sql)
        self.assertIn("last_heartbeat_at timestamptz", jobs_sql)

    def test_eval_runs_store_run_context(self):
        table_sql = self._table_sql("eval_runs")
        for snippet in [
            "skill_version_id text not null",
            "eval_set_id text not null",
            "environment_tags text[] not null",
            "run_context jsonb not null",
            "run_context_hash text not null",
        ]:
            self.assertIn(snippet, table_sql)
        for index in [
            "create index eval_runs_skill_version_id_idx",
            "create index eval_runs_context_hash_idx",
        ]:
            self.assertIn(index, self.normalized)
        self.assertNotIn("strategy", table_sql)

    def test_accepted_verifications_are_scoped_to_run_context(self):
        table_sql = self._table_sql("accepted_verifications")
        for snippet in [
            "skill_version_id text not null",
            "eval_set_id text not null",
            "run_context_hash text not null",
            "unique (skill_id, skill_version_id, eval_set_id, run_context_hash)",
        ]:
            self.assertIn(snippet, table_sql)
        self.assertIn(
            "foreign key (skill_version_id, skill_id) references skill_versions(id, skill_id)",
            self.normalized,
        )

    def test_foreign_key_columns_have_indexes(self):
        for index in [
            "create index skill_versions_skill_id_idx",
            "create index eval_case_versions_case_id_idx",
            "create index eval_set_cases_case_id_idx",
            "create index eval_runs_skill_version_id_idx",
            "create index eval_runs_eval_set_id_idx",
            "create index eval_runs_context_hash_idx",
            "create index case_results_case_version_id_idx",
            "create index eval_case_runs_case_version_id_idx",
            "create index eval_case_runs_job_id_idx",
            "create index skill_tags_group_value_idx",
            "create index tag_groups_sort_idx",
            "create index tag_values_group_sort_idx",
            "create index groups_scope_idx",
            "create index group_memberships_subject_idx",
            "create index role_assignments_subject_idx",
            "create index review_requests_skill_version_idx",
            "create index review_request_reviewers_actor_idx",
            "create index review_responses_reviewer_idx",
            "create index review_request_publish_targets_target_idx",
            "create index review_check_results_check_idx",
            "create index publish_targets_enabled_idx",
            "create index publish_records_skill_version_idx",
            "create index publish_records_target_status_idx",
            "create index notifications_recipient_idx",
        ]:
            self.assertIn(index, self.normalized)

    def test_skill_tags_groups_and_roles_support_group_tag_authorization(self):
        self.assertIn("create table skill_tags", self.normalized)
        self.assertIn("create table tag_groups", self.normalized)
        self.assertIn("create table tag_values", self.normalized)
        self.assertIn("create table groups", self.normalized)
        self.assertIn("create table group_memberships", self.normalized)
        self.assertIn("scope_type text not null default 'global'", self._table_sql("groups"))
        self.assertIn("scope_id text not null default 'default'", self._table_sql("groups"))
        self.assertIn("unique (scope_type, scope_id, name)", self._table_sql("groups"))
        self.assertIn("tag_group_id text not null", self._table_sql("skill_tags"))
        self.assertIn("tag_value text not null", self._table_sql("skill_tags"))
        self.assertIn("foreign key (tag_group_id, tag_value) references tag_values(tag_group_id, value)", self.normalized)
        self.assertIn("check (id ~ '^[a-za-z0-9_-]+$')", self._table_sql("tag_groups"))
        self.assertIn("resource_type text not null", self._table_sql("role_assignments"))
        self.assertIn("check (resource_type in ('skill', 'skill_tag'))", self._table_sql("role_assignments"))
        self.assertIn("check (subject_type in ('user', 'group'))", self._table_sql("role_assignments"))
        self.assertIn("check (role in ('admin', 'owner', 'maintainer', 'evaluator', 'reviewer', 'viewer'))", self._table_sql("role_assignments"))

    def test_review_and_publish_tables_exist(self):
        self.assertIn("skill_version_id text not null", self._table_sql("review_requests"))
        self.assertIn("foreign key (skill_version_id, skill_id) references skill_versions(id, skill_id)", self._table_sql("review_requests"))
        self.assertIn("score integer not null", self._table_sql("review_responses"))
        self.assertIn("check (score in (-1, 0, 1))", self._table_sql("review_responses"))
        self.assertIn("gate_expression jsonb not null default '{}'::jsonb", self._table_sql("publish_targets"))
        self.assertIn("auto_submit_on_pass boolean not null default true", self._table_sql("review_request_publish_targets"))
        self.assertIn("check_snapshot jsonb not null default '[]'::jsonb", self._table_sql("publish_records"))
        self.assertIn("check (status in ('pending_confirmation', 'released', 'cancelled', 'failed'))", self._table_sql("publish_records"))
        self.assertIn("recipient_actor_id text not null", self._table_sql("notifications"))

    def test_status_and_score_constraints_are_explicit(self):
        self.assertIn("constraint skills_lifecycle_status_check check (lifecycle_status in ('active', 'archived'))", self.normalized)
        self.assertNotIn("eval_sets_lifecycle_status_check", self.normalized)
        self.assertNotIn("eval_cases_lifecycle_status_check", self.normalized)
        self.assertIn("check (status in ('queued', 'running', 'finished', 'failed'))", self.normalized)
        self.assertIn("check (score in (0, 1))", self.normalized)

    def _table_sql(self, table: str) -> str:
        match = re.search(rf"create table {table} \((.*?)\);", self.normalized)
        self.assertIsNotNone(match, f"table not found: {table}")
        return match.group(1)


if __name__ == "__main__":
    unittest.main()
