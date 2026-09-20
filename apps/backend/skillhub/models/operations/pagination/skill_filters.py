"""将广场筛选及级联路径有效性表达为 SQL。"""
from collections import defaultdict

from sqlalchemy import Float, and_, case, cast, false, func, or_, select, true
from sqlalchemy.orm import aliased

from skillhub.models.schema import orm

from .common import contains


class SkillFilters:
    """目录可全量读取；Skill 匹配和统计始终在数据库执行。"""

    def __init__(self, connection):
        self.groups = connection.execute(orm.select_entity(orm.TagGroup)).mappings().all()
        self.values = connection.execute(orm.select_entity(orm.TagValue)).mappings().all()
        self.parents = {r["child_tag_group_id"]: r for r in connection.execute(
            orm.select_entity(orm.TagGroupCascade)).mappings()}

    def selected(self, group, value=None):
        tag = aliased(orm.SkillTag)
        query = select(tag.skill_id).where(tag.skill_id == orm.Skill.id, tag.tag_group_id == group)
        if value is not None:
            query = query.where(tag.tag_value == value)
        return query.correlate(orm.Skill).exists()

    def active(self, group, seen=frozenset()):
        if group in seen:
            return false()
        relation = self.parents.get(group)
        if relation is None:
            return true()
        parent = relation["parent_tag_group_id"]
        value = relation["parent_tag_value"] if relation["activation_mode"] == "parent_value" else None
        return and_(self.active(parent, seen | {group}), self.selected(parent, value))

    def tags(self, tags):
        groups = defaultdict(list)
        for tag in tags:
            groups[tag["group_id"]].append(tag["value"])
        return and_(true(), *(and_(self.active(group), or_(*(self.selected(group, value) for value in values)))
                             for group, values in groups.items()))

    def text(self, query):
        if not query:
            return true()
        tag = aliased(orm.SkillTag)
        tag_text = select(tag.skill_id).join(orm.TagGroup, orm.TagGroup.id == tag.tag_group_id).join(
            orm.TagValue, and_(orm.TagValue.tag_group_id == tag.tag_group_id, orm.TagValue.value == tag.tag_value)
        ).where(tag.skill_id == orm.Skill.id, contains(func.concat_ws(" ", tag.tag_group_id,
            orm.TagGroup.display_name, tag.tag_value, orm.TagValue.display_name), query)).correlate(orm.Skill).exists()
        return or_(contains(func.concat_ws(" ", orm.Skill.slug, orm.Skill.display_name, orm.Skill.owner_ref,
            orm.SkillVersion.change_summary, orm.SkillVersion.content_digest), query), tag_text)


def skill_query(actor, evaluations_visible=True):
    """构造与现有广场一致的最近完成测评、评分及更新时间。"""
    run = select(orm.EvalRun.summary, orm.EvalRun.created_at).join(
        orm.EvalSet, orm.EvalSet.id == orm.EvalRun.eval_set_id
    ).where(orm.EvalRun.skill_version_id == orm.Skill.current_version_id,
            orm.EvalSet.skill_id == orm.Skill.id, orm.EvalSet.name == "Primary",
            orm.EvalRun.status == "finished").order_by(
        orm.EvalRun.created_at.desc(), orm.EvalRun.id.desc()).limit(1).correlate(orm.Skill).lateral()
    query = orm.select_entity(orm.Skill).outerjoin(orm.SkillVersion, orm.SkillVersion.id == orm.Skill.current_version_id).outerjoin(run, true())
    verified = func.coalesce(cast(run.c.summary["total"].astext, Float), 0) > 0
    categories = {"all": true(), "workflow": select(orm.Workflow.id).where(orm.Workflow.skill_id == orm.Skill.id).exists(),
                  "verified": verified, "untested": ~verified, "mine": orm.Skill.owner_ref == actor}
    total = cast(run.c.summary["total"].astext, Float)
    score = case((total > 0, cast(run.c.summary["passed"].astext, Float) / total), else_=-1)
    times = [orm.Skill.updated_at, orm.SkillVersion.created_at]
    if evaluations_visible:
        times.append(run.c.created_at)
    updated = func.greatest(*times)
    orders = {"name": [orm.Skill.slug], "updated": [updated.desc()], "score": [score.desc(), updated.desc()]}
    return query.where(orm.Skill.lifecycle_status == "active"), categories, orders
