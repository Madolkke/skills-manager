"""独立的分页及轻量详情 REST 入口。"""
from typing import Annotated

from fastapi import Depends, FastAPI, Query

from skillhub.services.pagination import PaginationService
from skillhub.views.auth import ActorContext, actor_dependency, admin_key_dependency
from skillhub.views.dependencies import pagination_service_dependency
from skillhub.views.request_models.pagination import (
    PageResponse,
    ReviewPageQuery,
    ReviewPageResponse,
    RolePageQuery,
    RunPageQuery,
    SkillPageQuery,
    SkillPageResponse,
    VersionPageQuery,
)
from skillhub.views.request_models.pagination_items import (
    AdminOverviewResponse,
    GuidanceResponse,
    RoleSummary,
    RunListItem,
    SkillCoreResponse,
    VersionDetailResponse,
    VersionSummary,
)

Service = Annotated[PaginationService, Depends(pagination_service_dependency)]
Actor = Annotated[ActorContext, Depends(actor_dependency)]


def register_pagination_routes(app: FastAPI) -> None:
    """注册独立路径，不改变旧接口的返回结构。"""
    @app.post("/api/skills/query", response_model=SkillPageResponse)
    def skills(payload: SkillPageQuery, service: Service, actor: Actor):
        return service.skills(actor=actor.id, **payload.model_dump())

    @app.post("/api/admin/skills/query", response_model=SkillPageResponse, dependencies=[Depends(admin_key_dependency)])
    def admin_skills(payload: SkillPageQuery, service: Service):
        return service.skills(facets=False, **payload.model_dump())

    @app.get("/api/admin/role-assignments/page", response_model=PageResponse[RoleSummary], dependencies=[Depends(admin_key_dependency)])
    def roles(service: Service, query: Annotated[RolePageQuery, Query()]):
        return service.roles(**query.model_dump())

    @app.get("/api/admin/overview", response_model=AdminOverviewResponse, dependencies=[Depends(admin_key_dependency)])
    def overview(service: Service):
        return service.overview()

    @app.get("/api/skills/{skill_id}/core", response_model=SkillCoreResponse)
    def core(skill_id: str, service: Service, actor: Actor):
        return service.core(skill_id, actor.id)

    @app.get("/api/skills/{skill_id}/versions/page", response_model=PageResponse[VersionSummary])
    def versions(skill_id: str, service: Service, actor: Actor, query: Annotated[VersionPageQuery, Query()]):
        return service.versions(skill_id, **query.model_dump())

    @app.get("/api/skill-versions/{version_id}/detail", response_model=VersionDetailResponse)
    def version(version_id: str, service: Service, actor: Actor, include_files: bool = True):
        return service.version(version_id, include_files)

    @app.get("/api/skills/{skill_id}/reviews/page", response_model=ReviewPageResponse)
    def reviews(skill_id: str, service: Service, actor: Actor, query: Annotated[ReviewPageQuery, Query()]):
        return service.reviews(skill_id, **query.model_dump())

    @app.get("/api/reviews/{review_id}")
    def review(review_id: str, service: Service, actor: Actor):
        return service.review(review_id)

    @app.get("/api/skills/{skill_id}/eval-runs/page", response_model=PageResponse[RunListItem])
    def runs(skill_id: str, service: Service, actor: Actor, query: Annotated[RunPageQuery, Query()]):
        return service.runs(skill_id, **query.model_dump())

    @app.get("/api/skills/{skill_id}/guidance", response_model=GuidanceResponse)
    def guidance(skill_id: str, service: Service, actor: Actor):
        return service.guidance(skill_id)

    @app.get("/api/publish-targets/enabled")
    def targets(service: Service, actor: Actor):
        return service.targets()
