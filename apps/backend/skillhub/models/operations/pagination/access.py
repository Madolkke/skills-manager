"""后台授权分页与概览聚合。"""
from sqlalchemy import and_, case, func, literal, select

from skillhub.models.rules.tag_resources import encode_skill_tag_resource_id
from skillhub.models.schema import orm

from .common import contains, read_page


class AccessPageMixin:
    def _role_page_query(self, connection):
        """关联 Skill 名称；Tag 目录仅用于构造小型名称映射。"""
        tags = connection.execute(select(orm.TagValue.tag_group_id, orm.TagValue.value,
            orm.TagValue.display_name, orm.TagGroup.display_name.label("group_name"))
            .join(orm.TagGroup, orm.TagGroup.id == orm.TagValue.tag_group_id)).mappings().all()
        names = {encode_skill_tag_resource_id(t["tag_group_id"], t["value"]):
                 f'{t["group_name"]}: {t["display_name"] or t["value"]}' for t in tags}
        tag_label = case(names, value=orm.RoleAssignment.resource_id, else_=orm.RoleAssignment.resource_id) if names else orm.RoleAssignment.resource_id
        label = case((orm.RoleAssignment.resource_type == "global", literal("全部当前及未来 Skill")),
                     (orm.RoleAssignment.resource_type == "skill_tag", tag_label),
                     else_=func.coalesce(orm.Skill.display_name, orm.Skill.slug, orm.RoleAssignment.resource_id))
        missing = case((orm.RoleAssignment.resource_type == "skill", orm.Skill.id.is_(None)),
                       (orm.RoleAssignment.resource_type == "skill_tag", ~orm.RoleAssignment.resource_id.in_(names)), else_=False)
        query = select(*orm.entity_columns(orm.RoleAssignment), label.label("resource_label"), missing.label("resource_missing")).outerjoin(
            orm.Skill, and_(orm.RoleAssignment.resource_type == "skill", orm.RoleAssignment.resource_id == orm.Skill.id))
        return query, label

    def query_role_page(self, *, page=1, page_size=20, subject="", resource="", resource_type="", role=""):
        """服务端筛选授权，返回资源名称而非全量 Skill 依赖。"""
        with self._read_session() as connection:
            query, label = self._role_page_query(connection)
            query = query.where(contains(func.concat_ws(":", orm.RoleAssignment.subject_type, orm.RoleAssignment.subject_id), subject),
                                contains(func.concat_ws(" ", orm.RoleAssignment.resource_id, label), resource))
            if resource_type:
                query = query.where(orm.RoleAssignment.resource_type == resource_type)
            if role:
                query = query.where(orm.RoleAssignment.role == role)
            rows, meta = read_page(connection, query.order_by(orm.RoleAssignment.created_at.desc(), orm.RoleAssignment.id), page, page_size)
            return {**meta, "items": [self._row_dict(row) for row in rows]}

    def query_admin_overview(self):
        """后台首页只返回计数和有限条目。"""
        with self._read_session() as connection:
            counts = {name: connection.scalar(select(func.count()).select_from(entity).where(*conditions))
                      for name, entity, conditions in (
                          ("skills", orm.Skill, [orm.Skill.lifecycle_status == "active"]),
                          ("groups", orm.Group, [orm.Group.scope_type == "global"]),
                          ("tag_groups", orm.TagGroup, []), ("roles", orm.RoleAssignment, []))}
            groups = connection.execute(select(*orm.entity_columns(orm.TagGroup),
                select(func.count()).where(orm.TagValue.tag_group_id == orm.TagGroup.id).scalar_subquery().label("value_count"))
                .order_by(orm.TagGroup.updated_at.desc(), orm.TagGroup.id).limit(5)).mappings().all()
            roles, _ = self._role_page_query(connection)
            recent = connection.execute(roles.order_by(orm.RoleAssignment.created_at.desc(), orm.RoleAssignment.id).limit(8)).mappings().all()
            return {"counts": counts, "recent_tag_groups": [self._row_dict(r) for r in groups],
                    "recent_roles": [self._row_dict(r) for r in recent]}
