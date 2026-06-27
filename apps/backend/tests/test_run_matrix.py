import unittest

from skillhub.models.rules.run_matrix import build_eval_run_matrix


class RunMatrixBuilderTest(unittest.TestCase):
    def test_build_eval_run_matrix_merges_cases_versions_and_present_results(self):
        matrix = build_eval_run_matrix(
            skill={"id": "skill_1"},
            runs=[{"eval_run": {"id": "run-a"}}, {"eval_run": {"id": "run-b"}}],
            eval_set_cases_by_run={
                "run-a": [
                    {
                        "case": {"id": "case-a", "title": "A"},
                        "case_version": {"id": "case-a-v1", "version_number": 1},
                    },
                    {
                        "case": {"id": "case-b", "title": "B"},
                        "case_version": {"id": "case-b-v1", "version_number": 1},
                    },
                ],
                "run-b": [
                    {
                        "case": {"id": "case-a", "title": "A"},
                        "case_version": {"id": "case-a-v2", "version_number": 2},
                    },
                    {
                        "case": {"id": "case-b", "title": "B"},
                        "case_version": {"id": "case-b-v1", "version_number": 1},
                    },
                ],
            },
            results_by_run={
                "run-a": [{"case_version_id": "case-a-v1", "passed": False, "score": 0}],
                "run-b": [
                    {"case_version_id": "case-a-v2", "passed": True, "score": 1},
                    {"case_version_id": "case-b-v1", "passed": True, "score": 1},
                ],
            },
        )

        self.assertEqual(matrix["skill"], {"id": "skill_1"})
        self.assertEqual([row["case"]["id"] for row in matrix["cases"]], ["case-a", "case-b"])
        self.assertEqual(
            matrix["cases"][0]["versions"],
            [
                {"case_version_id": "case-a-v1", "version_number": 1},
                {"case_version_id": "case-a-v2", "version_number": 2},
            ],
        )
        self.assertEqual(matrix["cases"][1]["versions"], [{"case_version_id": "case-b-v1", "version_number": 1}])
        self.assertEqual(
            matrix["cells"],
            [
                {
                    "run_id": "run-a",
                    "case_id": "case-a",
                    "case_version_id": "case-a-v1",
                    "passed": False,
                    "score": 0,
                },
                {
                    "run_id": "run-b",
                    "case_id": "case-a",
                    "case_version_id": "case-a-v2",
                    "passed": True,
                    "score": 1,
                },
                {
                    "run_id": "run-b",
                    "case_id": "case-b",
                    "case_version_id": "case-b-v1",
                    "passed": True,
                    "score": 1,
                },
            ],
        )
