import unittest

from skillhub.application.in_memory import InMemoryWorkspace, SkillHubService
from skillhub.domain.errors import InvariantError
from skillhub.domain.models import ContentRef


def content_ref(name: str) -> ContentRef:
    return ContentRef(kind="skill_bundle", locator=f"memory:{name}", digest=f"digest-{name}")


class DomainInvariantTest(unittest.TestCase):
    def setUp(self) -> None:
        self.workspace = InMemoryWorkspace()
        self.service = SkillHubService(self.workspace)

    def create_skill(self, slug: str = "code-reviewer") -> str:
        skill = self.service.create_skill(
            slug=slug,
            owner_ref="skillhub-lab",
            variant_name="Variant A",
            variant_label="Baseline",
            variant_summary="Baseline maintained answer.",
            tags=["codex"],
            content_ref=content_ref(f"{slug}-v1"),
            change_summary="Initial version.",
            actor="tester",
        )
        return skill.id

    def test_candidate_variant_version_can_be_evaluated_before_promotion(self):
        skill_id = self.create_skill()
        variant = next(item for item in self.workspace.variants.values() if item.skill_id == skill_id)
        eval_set = next(item for item in self.workspace.eval_sets.values() if item.skill_id == skill_id)
        eval_set_version = self.service.create_eval_case(
            skill_id=skill_id,
            title="PR: missing owner check",
            input_text="diff --git a/api.ts b/api.ts",
            expected_output="Should flag missing ownerId filter.",
        )

        candidate = self.service.create_variant_version(
            variant_id=variant.id,
            content_ref=content_ref("candidate"),
            change_summary="Tighten authorization review.",
            actor="tester",
            make_current=False,
        )

        self.assertNotEqual(self.workspace.variants[variant.id].current_version_id, candidate.id)
        run = self.service.record_eval_run(
            variant_version_id=candidate.id,
            eval_set_version_id=eval_set_version.id,
            strategy="manual_pass_fail",
            results={eval_set_version.case_version_ids[0]: True},
            actor="tester",
        )

        self.assertEqual(run.variant_version_id, candidate.id)
        self.assertEqual(run.eval_set_version_id, self.workspace.eval_sets[eval_set.id].current_version_id)
        self.assertEqual(self.workspace.case_results[0].passed, True)

    def test_eval_case_version_creates_new_eval_set_snapshot_without_mutating_history(self):
        skill_id = self.create_skill()
        first_set = self.service.create_eval_case(
            skill_id=skill_id,
            title="PR: null nickname",
            input_text="old input",
            expected_output="old expectation",
        )
        old_case_version_id = first_set.case_version_ids[0]
        case = next(iter(self.workspace.eval_cases.values()))

        new_case_version = self.service.create_eval_case_version(
            case_id=case.id,
            input_text="new input",
            expected_output="new expectation",
        )
        latest_eval_set = next(item for item in self.workspace.eval_sets.values() if item.skill_id == skill_id)
        latest_set_version = self.workspace.eval_set_versions[latest_eval_set.current_version_id]

        self.assertEqual(first_set.case_version_ids, (old_case_version_id,))
        self.assertEqual(latest_set_version.case_version_ids, (new_case_version.id,))
        self.assertNotEqual(first_set.id, latest_set_version.id)

    def test_eval_run_rejects_cross_skill_variant_and_eval_set(self):
        first_skill = self.create_skill("code-reviewer")
        second_skill = self.create_skill("security-reviewer")
        first_variant = next(item for item in self.workspace.variants.values() if item.skill_id == first_skill)
        second_eval_set_version = self.service.create_eval_case(
            skill_id=second_skill,
            title="Error response leaks token",
            input_text="diff",
            expected_output="Flag token leak.",
        )

        with self.assertRaisesRegex(InvariantError, "same skill"):
            self.service.record_eval_run(
                variant_version_id=self.workspace.variants[first_variant.id].current_version_id,
                eval_set_version_id=second_eval_set_version.id,
                strategy="manual_pass_fail",
                results={},
                actor="tester",
            )

    def test_promotion_rejects_version_from_another_variant(self):
        skill_id = self.create_skill()
        first_variant = next(item for item in self.workspace.variants.values() if item.skill_id == skill_id)
        second_variant = self.service.create_variant(
            skill_id=skill_id,
            name="Variant B",
            label="OpenCode",
            summary="OpenCode maintained answer.",
            tags=["opencode"],
            content_ref=content_ref("opencode-v1"),
            change_summary="Initial OpenCode version.",
            actor="tester",
        )

        with self.assertRaisesRegex(InvariantError, "own version"):
            self.service.promote_variant_version(
                variant_id=first_variant.id,
                version_id=second_variant.current_version_id,
            )


if __name__ == "__main__":
    unittest.main()
