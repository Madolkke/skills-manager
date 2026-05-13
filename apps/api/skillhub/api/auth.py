from __future__ import annotations

from dataclasses import dataclass

from fastapi import Header

from skillhub.domain.errors import InvariantError

ACTOR_HEADER = "X-SkillHub-Actor"
DEFAULT_LOCAL_ACTOR = "product-operator"


@dataclass(frozen=True)
class ActorContext:
    id: str
    subject_type: str = "user"


def actor_dependency(x_skillhub_actor: str | None = Header(default=None, alias=ACTOR_HEADER)) -> ActorContext:
    actor = (x_skillhub_actor or DEFAULT_LOCAL_ACTOR).strip()
    if not actor:
        raise InvariantError("Actor identity cannot be blank.")
    return ActorContext(id=actor)
