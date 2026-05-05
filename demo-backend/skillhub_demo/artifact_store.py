from __future__ import annotations

from pathlib import Path
from typing import Protocol, Union


PathLike = Union[str, Path]


class ArtifactStore(Protocol):
    label: str

    def write_text(self, namespace: str, content_hash: str, content: str) -> str:
        ...

    def read_text(self, locator: str) -> str:
        ...


class FileArtifactStore:
    def __init__(self, root: PathLike):
        self.root = Path(root)
        self.label = "file:%s" % self.root

    def write_text(self, namespace: str, content_hash: str, content: str) -> str:
        clean_namespace = _clean_namespace(namespace)
        relative_path = Path(clean_namespace) / ("%s.json" % content_hash)
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text(content, encoding="utf-8")
        return "file:%s" % relative_path.as_posix()

    def read_text(self, locator: str) -> str:
        if not locator.startswith("file:"):
            raise ValueError("Unsupported artifact locator: %s" % locator)
        relative = locator.removeprefix("file:")
        parts = [part for part in relative.split("/") if part]
        if not parts or any(part == ".." for part in parts):
            raise ValueError("Invalid artifact locator: %s" % locator)
        return (self.root / Path(*parts)).read_text(encoding="utf-8")


def _clean_namespace(namespace: str) -> str:
    parts = [part for part in namespace.strip().split("/") if part]
    if not parts or any(part == ".." for part in parts):
        raise ValueError("Invalid artifact namespace: %s" % namespace)
    return "/".join(parts)
