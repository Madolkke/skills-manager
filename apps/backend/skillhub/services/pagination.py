"""前端按需读取服务，复用原资源身份及权限语义。"""
from typing import Any

from skillhub.models.store import SkillHubStore
from skillhub.services.base import ServiceBase


class PaginationService(ServiceBase[SkillHubStore]):
    def skills(self, **options) -> dict[str, Any]:
        """查询 Skill 页及筛选统计。"""
        return self.store.query_skill_page(**options)

    def roles(self, **options) -> dict[str, Any]:
        """查询授权页及资源名称。"""
        return self.store.query_role_page(**options)

    def overview(self) -> dict[str, Any]:
        """读取后台概览。"""
        return self.store.query_admin_overview()

    def core(self, skill_id: str, actor: str) -> dict[str, Any]:
        """读取不含历史版本的基础详情。"""
        return self.store.query_skill_core(skill_id=skill_id, actor=actor)

    def versions(self, skill_id: str, **options) -> dict[str, Any]:
        """读取版本摘要页。"""
        return self.store.query_version_page(skill_id=skill_id, **options)

    def version(self, version_id: str, include_files: bool = True) -> dict[str, Any]:
        """读取选中版本与前版。"""
        return self.store.query_version_detail(version_id=version_id, include_files=include_files)

    def reviews(self, skill_id: str, **options) -> dict[str, Any]:
        """读取单个 Skill 的评审摘要页。"""
        return self.store.query_review_page(skill_id=skill_id, **options)

    def review(self, review_id: str) -> dict[str, Any]:
        """读取选中评审详情。"""
        return self.store.query_review_detail(review_id=review_id)

    def runs(self, skill_id: str, **options) -> dict[str, Any]:
        """读取运行历史页。"""
        return self.store.query_run_page(skill_id=skill_id, **options)

    def guidance(self, skill_id: str) -> dict[str, Any]:
        """读取概览展示的有限条目。"""
        return self.store.query_skill_guidance(skill_id=skill_id)

    def targets(self) -> list[dict[str, Any]]:
        """读取公开的启用发布目标目录。"""
        return [target for target in self.store.list_publish_targets() if target["enabled"]]
