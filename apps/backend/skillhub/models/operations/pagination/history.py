"""评审与测评历史的摘要分页，详情独立查询。"""
from sqlalchemy import func, select

from skillhub.models.schema import orm

from .common import read_page


class HistoryPageMixin:
    def query_review_page(self, *, skill_id, page=1, page_size=20, status=""):
        """只查询评审摘要与本页版本，计数覆盖完整历史。"""
        with self._read_session() as connection:
            self._skill_row(connection, skill_id)
            query = orm.select_entity(orm.ReviewRequest).where(orm.ReviewRequest.skill_id == skill_id)
            counts = dict(connection.execute(select(orm.ReviewRequest.status, func.count()).where(
                orm.ReviewRequest.skill_id == skill_id).group_by(orm.ReviewRequest.status)).all())
            if status:
                query = query.where(orm.ReviewRequest.status == status)
            rows, meta = read_page(connection, query.order_by(orm.ReviewRequest.created_at.desc(), orm.ReviewRequest.id.desc()), page, page_size)
            versions = {r["id"]: self._row_dict(r) for r in connection.execute(orm.select_entity(orm.SkillVersion).where(
                orm.SkillVersion.id.in_([r["skill_version_id"] for r in rows]))).mappings()}
            return {**meta, "counts": counts, "items": [{**self._row_dict(r), "skill_version": versions[r["skill_version_id"]]} for r in rows]}

    def query_review_detail(self, *, review_id):
        """沿用原评审读取权限语义，按 ID 返回详情。"""
        with self._read_session() as connection:
            return self._review_detail(connection, self._review_row(connection, review_id))

    def query_run_page(self, *, skill_id, page=1, page_size=20, eval_set_id=None, status=None, skill_version_id=None):
        """运行摘要分页不读取测试例结果。"""
        with self._read_session() as connection:
            self._skill_row(connection, skill_id)
            query = orm.select_entity(orm.EvalRun).where(orm.EvalRun.skill_id == skill_id)
            for column, value in ((orm.EvalRun.eval_set_id, eval_set_id), (orm.EvalRun.status, status),
                                  (orm.EvalRun.skill_version_id, skill_version_id)):
                if value:
                    query = query.where(column == value)
            rows, meta = read_page(connection, query.order_by(orm.EvalRun.created_at.desc(), orm.EvalRun.id.desc()), page, page_size)
            versions = {r["id"]: self._row_dict(r) for r in connection.execute(orm.select_entity(orm.SkillVersion).where(
                orm.SkillVersion.id.in_([r["skill_version_id"] for r in rows]))).mappings()}
            sets = {r["id"]: self._row_dict(r) for r in connection.execute(orm.select_entity(orm.EvalSet).where(
                orm.EvalSet.id.in_([r["eval_set_id"] for r in rows]))).mappings()}
            return {**meta, "items": [{"eval_run": self._row_dict(r), "skill_version": versions[r["skill_version_id"]],
                                      "eval_set": sets[r["eval_set_id"]]} for r in rows]}
