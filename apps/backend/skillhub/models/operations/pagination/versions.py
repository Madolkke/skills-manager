"""版本摘要、语义版本定位及轻量 Skill 详情。"""
from sqlalchemy import ARRAY, Numeric, func, literal_column, select, tuple_

from skillhub.models.schema import orm

from .common import contains, read_page


def semantic_key():
    """PostgreSQL 中比较 SemVer，构建元信息不参与优先级。"""
    core = func.split_part(orm.SkillVersion.version, "-", 1)
    core = func.split_part(core, "+", 1)
    prerelease = literal_column("""ARRAY(SELECT CASE WHEN part ~ '^[0-9]+$'
        THEN '0' || lpad(length(part)::text, 10, '0') || part ELSE '1' || part END
        FROM unnest(string_to_array(substring(split_part(skill_versions.version, '+', 1) from '^[^-]+-(.*)$'), '.'))
        WITH ORDINALITY AS p(part, position) ORDER BY position)""")
    return tuple_(func.string_to_array(core, ".").cast(ARRAY(Numeric)),
                  ~orm.SkillVersion.version.op("~")("^[^-]+-"), prerelease, orm.SkillVersion.version_number)


class VersionPageMixin:
    def query_version_page(self, *, skill_id, page=1, page_size=20, query=""):
        """版本列表只返回元信息，不读取 artifact 内容。"""
        with self._read_session() as connection:
            self._skill_row(connection, skill_id)
            statement = orm.select_entity(orm.SkillVersion).where(orm.SkillVersion.skill_id == skill_id,
                contains(func.concat_ws(" ", orm.SkillVersion.version, orm.SkillVersion.display_name, orm.SkillVersion.change_summary), query))
            rows, meta = read_page(connection, statement.order_by(orm.SkillVersion.version_number.desc(), orm.SkillVersion.id), page, page_size)
            return {**meta, "items": [self._row_dict(row) for row in rows]}

    def query_version_detail(self, *, version_id, include_files=True):
        """按 ID 读取文件及跨页的语义前版摘要。"""
        with self._read_session() as connection:
            version = self._skill_version_row(connection, version_id)
            key = select(*semantic_key().clauses).where(orm.SkillVersion.id == version_id).scalar_subquery()
            previous = connection.execute(orm.select_entity(orm.SkillVersion).where(
                orm.SkillVersion.skill_id == version["skill_id"], semantic_key() < key)
                .order_by(semantic_key().desc(), orm.SkillVersion.id).limit(1)).mappings().one_or_none()
            return {"version": self._skill_version_detail(connection, version) if include_files else self._row_dict(version),
                    "previous": self._row_dict(previous) if previous else None}

    def query_skill_core(self, *, skill_id, actor):
        """基础详情没有完整版本列表与文件，明确提供版本计数和最高版本。"""
        detail = self.skill_detail(skill_id, actor, lightweight=True)
        with self._read_session() as connection:
            base = orm.select_entity(orm.SkillVersion).where(orm.SkillVersion.skill_id == skill_id)
            highest = connection.execute(base.order_by(semantic_key().desc(), orm.SkillVersion.id).limit(1)).mappings().one_or_none()
            detail["version_count"] = connection.scalar(select(func.count()).select_from(orm.SkillVersion).where(orm.SkillVersion.skill_id == skill_id))
            detail["highest_version"] = self._row_dict(highest) if highest else None
        detail.pop("versions")
        return detail

    def query_skill_guidance(self, *, skill_id):
        """只读取概览显示的四个版本及当前版本状态。"""
        with self._read_session() as connection:
            skill = self._skill_row(connection, skill_id)
            rows = connection.execute(orm.select_entity(orm.SkillVersion).where(orm.SkillVersion.skill_id == skill_id)
                .order_by(orm.SkillVersion.version_number.desc()).limit(4)).mappings().all()
            ids = list({*[r["id"] for r in rows], skill["current_version_id"]} - {None})
            reviews = connection.execute(select(*orm.entity_columns(orm.ReviewRequest),
                select(func.count()).where(orm.ReviewResponse.review_request_id == orm.ReviewRequest.id).scalar_subquery().label("response_count"),
                select(func.count()).where(orm.ReviewRequestReviewer.review_request_id == orm.ReviewRequest.id).scalar_subquery().label("reviewer_count")
                ).where(orm.ReviewRequest.skill_version_id.in_(ids))
                .distinct(orm.ReviewRequest.skill_version_id).order_by(orm.ReviewRequest.skill_version_id,
                    orm.ReviewRequest.created_at.desc(), orm.ReviewRequest.id.desc())).mappings().all()
            published = connection.execute(select(orm.PublishRecord.skill_version_id, orm.PublishRecord.status, func.count().label("count"))
                .where(orm.PublishRecord.skill_version_id.in_(ids)).group_by(orm.PublishRecord.skill_version_id, orm.PublishRecord.status)).mappings().all()
            runs = connection.execute(orm.select_entity(orm.EvalRun).where(orm.EvalRun.skill_version_id.in_(ids))
                .distinct(orm.EvalRun.skill_version_id).order_by(orm.EvalRun.skill_version_id,
                    orm.EvalRun.created_at.desc(), orm.EvalRun.id.desc())).mappings().all()
            return {"versions": [self._row_dict(r) for r in rows], "reviews": [self._row_dict(r) for r in reviews],
                    "publish_records": [dict(r) for r in published], "eval_runs": [self._row_dict(r) for r in runs]}
