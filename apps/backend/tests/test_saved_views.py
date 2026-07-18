import unittest

from skillhub.models.errors import InvariantError
from skillhub.models.rules.saved_views import normalize_saved_view_config, validate_saved_view_type


class SavedViewConfigTest(unittest.TestCase):
    def test_normalize_saved_view_config_keeps_supported_non_default_strings(self):
        config = normalize_saved_view_config(
            {
                "skill_version_id": " version-a ",
                "eval_set_id": "all",
                "matrix_show_summary": "false",
                "compare_candidate_run_id": "run-candidate",
                "unknown": "kept?",
                "status": "",
                "matrix_show_score": False,
            }
        )

        self.assertEqual(
            config,
            {
                "skill_version_id": "version-a",
                "matrix_show_summary": "false",
                "compare_candidate_run_id": "run-candidate",
            },
        )

    def test_validate_saved_view_type_accepts_run_history(self):
        validate_saved_view_type("run_history")

    def test_validate_saved_view_type_rejects_unknown_type(self):
        with self.assertRaises(InvariantError):
            validate_saved_view_type("dashboard")
