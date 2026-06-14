from __future__ import annotations

from fastapi import Depends, FastAPI, Response

from skillhub.api.auth import (
    ActorContext,
    DEFAULT_LOCAL_ACTOR,
    actor_dependency,
    clear_actor_cookie,
    normalize_actor,
    set_actor_cookie,
    verify_local_session_access_code,
)
from skillhub.api.schemas import SetSessionPayload


def register_session_routes(app: FastAPI) -> None:
    @app.get("/api/session")
    def current_session(actor: ActorContext = Depends(actor_dependency)):
        return {"actor": actor.id, "subject_type": actor.subject_type}

    @app.post("/api/session")
    def set_session(payload: SetSessionPayload, response: Response):
        verify_local_session_access_code(payload.access_code)
        actor = normalize_actor(payload.actor)
        set_actor_cookie(response, actor)
        return {"actor": actor, "subject_type": "user"}

    @app.delete("/api/session")
    def clear_session(response: Response):
        clear_actor_cookie(response)
        return {"actor": DEFAULT_LOCAL_ACTOR, "subject_type": "user"}
