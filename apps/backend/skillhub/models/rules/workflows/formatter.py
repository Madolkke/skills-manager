from __future__ import annotations

from copy import deepcopy
from typing import Any


def format_workflow_document(document: dict[str, Any]) -> dict[str, Any]:
    """Return the external Workflow representation."""
    # Replace this identity transformation when the target format is finalized.
    return deepcopy(document)
