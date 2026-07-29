from __future__ import annotations

from typing import Any

from .checker import SAMPLE_INDEX_DIAGNOSTIC_CODES, validate_expression
from .environment import workflow_expression_environment


def workflow_sample_index_diagnostics(
    document: dict[str, Any],
    steps: list[dict[str, Any]],
) -> list[tuple[dict[str, Any], dict[str, str]]]:
    """Return sample-index diagnostics with their Workflow transition selections."""
    environment = workflow_expression_environment(document)
    results: list[tuple[dict[str, Any], dict[str, str]]] = []
    for step in steps:
        for transition in step["topology"]:
            source = transition["conditionExpression"]
            if not source.strip():
                continue
            selection = {
                "type": "step",
                "id": step["id"],
                "section": "paths",
                "itemId": transition["id"],
                "field": "conditionExpression",
            }
            results.extend(
                (diagnostic, selection)
                for diagnostic in validate_expression(source, environment)["diagnostics"]
                if diagnostic["code"] in SAMPLE_INDEX_DIAGNOSTIC_CODES
            )
    return results
