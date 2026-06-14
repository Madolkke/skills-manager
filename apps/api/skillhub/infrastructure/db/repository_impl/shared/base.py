from __future__ import annotations

from sqlalchemy import Engine


class RepositoryBase:
    def __init__(self, engine: Engine):
        self.engine = engine
