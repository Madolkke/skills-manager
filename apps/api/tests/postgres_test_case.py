from __future__ import annotations

import unittest
from os import environ

from skillhub.api.database import create_postgres_engine, resolve_database_url
from skillhub.infrastructure.db.tables import metadata


class PostgresTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_postgres_engine(resolve_database_url(environ))
        metadata.drop_all(self.engine)
        metadata.create_all(self.engine)

    def tearDown(self) -> None:
        metadata.drop_all(self.engine)
        self.engine.dispose()
