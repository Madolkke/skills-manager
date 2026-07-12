from skillhub.views import schemas
from skillhub.views.request_models.admin import AdminGroupPayload
from skillhub.views.request_models.evaluations import CreateEvalCasePayload
from skillhub.views.request_models.reviews import CreateReviewRequestPayload
from skillhub.views.request_models.skills import CreateSkillPayload
from skillhub.views.request_models.workflows import SaveWorkflowPayload


def test_legacy_schema_facade_exports_domain_models() -> None:
    assert schemas.AdminGroupPayload is AdminGroupPayload
    assert schemas.CreateEvalCasePayload is CreateEvalCasePayload
    assert schemas.CreateReviewRequestPayload is CreateReviewRequestPayload
    assert schemas.CreateSkillPayload is CreateSkillPayload
    assert schemas.SaveWorkflowPayload is SaveWorkflowPayload


def test_resource_models_keep_strict_extra_field_policy() -> None:
    try:
        SaveWorkflowPayload(document={}, unexpected=True)
    except Exception as exc:
        assert "unexpected" in str(exc)
    else:
        raise AssertionError("Admin request schema accepted an unknown field")
