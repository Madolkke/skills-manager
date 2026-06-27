from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar


StoreT = TypeVar("StoreT")


@dataclass(slots=True)
class ServiceBase(Generic[StoreT]):
    store: StoreT
