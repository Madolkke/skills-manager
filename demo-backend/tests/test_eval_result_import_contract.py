import json
import unittest
from pathlib import Path

from skillhub_demo.eval_result_import import load_eval_result_import_schema, validate_eval_result_import_shape
from skillhub_demo.seed import create_seed_data
from skillhub_demo.store import SkillHubStore


REPO_ROOT = Path(__file__).resolve().parents[2]


class EvalResultImportContractTest(unittest.TestCase):
    def test_schema_is_loadable_and_names_required_fields(self):
        schema = load_eval_result_import_schema()

        self.assertEqual(schema["title"], "SkillHub Eval Result Import")
        self.assertEqual(
            schema["required"],
            ["variant_version_id", "eval_set_version_id", "strategy_ref", "results"],
        )
        self.assertEqual(schema["properties"]["results"]["additionalProperties"]["type"], "boolean")

    def test_fixture_matches_contract_and_imports_against_seed_data(self):
        payload = self._fixture("eval-result-import.code-reviewer.json")

        validate_eval_result_import_shape(payload)
        result = SkillHubStore(create_seed_data()).import_eval_result(payload)

        self.assertEqual(result["eval_run"]["strategy_ref"], "external-script-v1")
        self.assertEqual(result["result_counts"], {"passed": 2, "failed": 1, "missing": 0, "total": 3})

    def test_contract_rejects_string_booleans(self):
        payload = self._fixture("eval-result-import.code-reviewer.json")
        payload["results"]["casever-null-v1"] = "true"

        with self.assertRaisesRegex(ValueError, "booleans"):
            validate_eval_result_import_shape(payload)

    def _fixture(self, name):
        with (REPO_ROOT / "fixtures" / name).open("r", encoding="utf-8") as file:
            return json.load(file)


if __name__ == "__main__":
    unittest.main()
