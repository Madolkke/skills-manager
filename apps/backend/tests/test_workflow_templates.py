import pytest
from pydantic import ValidationError

from skillhub.models.rules.workflows.schema import Conclusion
from skillhub.models.rules.workflows.templates import validate_template


def test_template_scanner_supports_plain_text_and_multiple_expressions() -> None:
    environment = {"inputs": {}, "outputs": {"status": {"sampleCount": 1, "schema": {"type": "string"}}}, "config": {}}
    diagnostics = validate_template("状态：{{ outputs.status }}；{{ 1 + 2 }}", environment)
    assert diagnostics == []


def test_conclusion_severity_defaults_and_rejects_unknown_values() -> None:
    base = {"id": "conclusion-1", "name": "完成", "rootCause": "", "repairRecommendation": "", "nodeType": "conclusion"}
    assert Conclusion.model_validate(base).severity == "info"
    with pytest.raises(ValidationError):
        Conclusion.model_validate({**base, "severity": "fatal"})


def test_template_scanner_reports_unclosed_and_unknown_expression() -> None:
    environment = {"inputs": {}, "outputs": {}, "config": {}}
    diagnostics = validate_template("{{ outputs.missing }} {{", environment)
    assert [item["code"] for item in diagnostics] == ["UNKNOWN_PROPERTY", "TEMPLATE_UNCLOSED", "TEMPLATE_EMPTY_EXPRESSION"]
