"""广场与后台 Skill 分页读模型。"""
from sqlalchemy import and_, func

from skillhub.models.schema import orm

from .common import read_page
from .skill_filters import SkillFilters, skill_query


class SkillPageMixin:
    def query_skill_page(self, *, actor="", page=1, page_size=20, query="", category="all", sort="updated",
                         tags=None, evaluations_visible=True, diagnostic_group=None, diagnostic_kind=None,
                         facets=True):
        """先分页，再批量投影当前页；分面通过聚合返回。"""
        with self._read_session() as connection:
            catalog = SkillFilters(connection)
            base, categories, orders = skill_query(actor, evaluations_visible)
            predicate = and_(catalog.text(query.strip()), categories[category])
            if diagnostic_group:
                active, selected = catalog.active(diagnostic_group), catalog.selected(diagnostic_group)
                predicate = and_(predicate, (~active & selected) if diagnostic_kind == "orphaned" else (active & ~selected))
            filtered = base.where(predicate, catalog.tags(tags or []))
            rows, meta = read_page(connection, filtered.order_by(*orders[sort], orm.Skill.id), page, page_size)
            result = {**meta, "items": self._skill_list_items(connection, rows, include_files=False)}
            if facets:
                counts = connection.execute(base.with_only_columns(*(
                    func.count().filter(condition).label(key) for key, condition in categories.items()
                ), maintain_column_froms=True)).mappings().one()
                selected_tags = tags or []
                expressions, keys = [], []
                for value in catalog.values:
                    tag = {"group_id": value["tag_group_id"], "value": value["value"]}
                    candidate = selected_tags if tag in selected_tags else [*selected_tags, tag]
                    expressions.append(func.count().filter(and_(predicate, catalog.tags(candidate))).label(f"t{len(keys)}"))
                    keys.append(f'{tag["group_id"]}\u0000{tag["value"]}')
                values = connection.execute(base.with_only_columns(*expressions, maintain_column_froms=True)).one() if expressions else []
                result.update(counts=dict(counts), tag_counts=dict(zip(keys, values)))
            return result
