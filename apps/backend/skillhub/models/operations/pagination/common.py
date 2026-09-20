"""分页查询共用的数据库边界，不装配全量实体。"""
from sqlalchemy import func, select


def read_page(connection, query, page=1, page_size=20):
    """在数据库计数并读取指定页，返回映射行与分页元信息。"""
    total = connection.scalar(select(func.count()).select_from(query.order_by(None).subquery())) or 0
    rows = connection.execute(query.offset((page - 1) * page_size).limit(page_size)).mappings().all()
    return rows, {"total": total, "page": page, "page_size": page_size}


def contains(column, value):
    """按字面子串匹配，避免用户输入被解释为 LIKE 通配符。"""
    return func.lower(func.coalesce(column, "")).contains(value.lower(), autoescape=True)
