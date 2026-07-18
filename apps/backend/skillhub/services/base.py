from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Generic, Iterator, TypeVar

StoreT = TypeVar("StoreT")


@dataclass(slots=True)
class ServiceBase(Generic[StoreT]):
    store: StoreT

    @contextmanager
    def transaction_store(self) -> Iterator[StoreT]:
        transaction = getattr(self.store, "transaction", None)
        if transaction is None:
            yield self.store
            return
        with transaction() as store:
            yield store
