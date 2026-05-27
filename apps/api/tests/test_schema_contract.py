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
            "eval_set_versions",
            "eval_set_case_versions",
            "eval_runs",
            "case_results",
            "accepted_verifications",
            "saved_views",
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
            "foreign key (eval_set_version_id, skill_id) references eval_set_versions(id, skill_id)",
            self.normalized,
        )
        self.assertIn("constraint skill_versions_id_skill_unique unique (id, skill_id)", self.normalized)
        self.assertIn("constraint eval_set_versions_id_skill_unique unique (id, skill_id)", self.normalized)
        self.assertIn(
            "foreign key (current_version_id, id) references skill_versions(id, skill_id)",
            self.normalized,
        )

    def test_eval_set_membership_references_case_versions_not_cases(self):
        self.assertIn("create table eval_set_case_versions", self.normalized)
        self.assertIn(
            "foreign key (case_version_id, skill_id) references eval_case_versions(id, skill_id)",
            self.normalized,
        )
        self.assertNotIn("case_id text not null", self._table_sql("eval_set_case_versions"))

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

    def test_append_only_version_uniqueness_constraints_exist(self):
        for constraint in [
            "unique (skill_id, version_number)",
            "unique (case_id, version_number)",
            "unique (eval_set_id, version_number)",
            "primary key (run_id, case_version_id)",
        ]:
            self.assertIn(constraint, self.normalized)

    def test_versions_have_optional_display_names(self):
        self.assertIn("display_name text", self._table_sql("skill_versions"))
        self.assertIn("display_name text", self._table_sql("eval_set_versions"))

    def test_eval_runs_store_run_context(self):
        table_sql = self._table_sql("eval_runs")
        for snippet in [
            "skill_version_id text not null",
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

    def test_accepted_verifications_are_scoped_to_run_context(self):
        table_sql = self._table_sql("accepted_verifications")
        for snippet in [
            "skill_version_id text not null",
            "run_context_hash text not null",
            "unique (skill_id, skill_version_id, eval_set_version_id, run_context_hash)",
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
            "create index eval_set_versions_eval_set_id_idx",
            "create index eval_runs_skill_version_id_idx",
            "create index eval_runs_eval_set_version_id_idx",
            "create index eval_runs_context_hash_idx",
            "create index case_results_case_version_id_idx",
        ]:
            self.assertIn(index, self.normalized)

    def test_status_and_score_constraints_are_explicit(self):
        self.assertIn("check (lifecycle_status in ('active', 'archived'))", self.normalized)
        self.assertIn("check (status in ('queued', 'running', 'finished', 'failed'))", self.normalized)
        self.assertIn("check (score in (0, 1))", self.normalized)

    def _table_sql(self, table: str) -> str:
        match = re.search(rf"create table {table} \((.*?)\);", self.normalized)
        self.assertIsNotNone(match, f"table not found: {table}")
        return match.group(1)


if __name__ == "__main__":
    unittest.main()
