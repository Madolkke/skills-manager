from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker


class StoreBase:
    def __init__(self, bind: Engine | Session):
        self._session = bind if isinstance(bind, Session) else None
        self._engine = bind.get_bind() if isinstance(bind, Session) else bind
        self._session_factory = sessionmaker(
            bind=self._engine,
            autoflush=False,
            expire_on_commit=False,
        )

    @property
    def engine(self) -> Engine:
        return self._engine

    @property
    def session(self) -> Session | None:
        return self._session

    @contextmanager
    def _read_session(self) -> Iterator[Session]:
        if self._session is not None:
            yield self._session
            return
        with self._session_factory() as session:
            yield session

    @contextmanager
    def _write_session(self) -> Iterator[Session]:
        if self._session is not None:
            yield self._session
            return
        with self._session_factory.begin() as session:
            yield session
