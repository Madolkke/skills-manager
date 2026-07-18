from __future__ import annotations

import unittest
from os import environ

from sqlalchemy import text
from sqlalchemy.orm import Session

from skillhub.models.schema.database import create_postgres_engine, resolve_database_url
from skillhub.models.schema.migrations import stamp_database
from skillhub.models.schema.reference_data import seed_reference_data
from skillhub.models.schema.tables import metadata
from tests.conftest import ensure_postgres_test_database


class PostgresTestCase(unittest.TestCase):
    def setUp(self) -> None:
        ensure_postgres_test_database()
        self.engine = create_postgres_engine(resolve_database_url(environ))
        metadata.drop_all(self.engine)
        with self.engine.begin() as connection:
            connection.execute(text("drop table if exists alembic_version"))
        metadata.create_all(self.engine)
        with Session(self.engine) as session, session.begin():
            seed_reference_data(session)
        stamp_database(self.engine)

    def tearDown(self) -> None:
        metadata.drop_all(self.engine)
        with self.engine.begin() as connection:
            connection.execute(text("drop table if exists alembic_version"))
        self.engine.dispose()
