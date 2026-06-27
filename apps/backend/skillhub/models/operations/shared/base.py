from __future__ import annotations

from sqlalchemy import Engine


class StoreBase:
    def __init__(self, engine: Engine):
        self.engine = engine
