from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, Field

SAVED_VIEW_NAME_MAX_LENGTH = 80
SavedViewName = Annotated[str, Field(min_length=1, max_length=SAVED_VIEW_NAME_MAX_LENGTH)]


class CreateSavedViewPayload(BaseModel):
    skill_id: str
    name: SavedViewName
    view_type: str = "run_history"
    config: dict[str, str] = Field(default_factory=dict)


class SetSessionPayload(BaseModel):
    actor: str
    access_code: str
