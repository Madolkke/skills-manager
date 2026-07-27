from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from skillhub.models.errors import InvariantError

EMPTY_OPTIONS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {},
    "additionalProperties": False,
}


@dataclass(frozen=True)
class WorkflowSkillGeneratorDescriptor:
    id: str
    version: str
    label: str
    default: bool
    options_schema: dict[str, Any]

    def to_payload(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "version": self.version,
            "label": self.label,
            "default": self.default,
            "options_schema": self.options_schema.copy(),
        }


@dataclass(frozen=True)
class WorkflowSkillGeneratorContext:
    slug: str
    document: dict[str, Any]


@dataclass(frozen=True)
class GeneratedSkillFile:
    path: str
    content_text: str

    def to_payload(self) -> dict[str, str]:
        return {"path": self.path, "content_text": self.content_text}


@dataclass(frozen=True)
class WorkflowSkillGeneratorResult:
    descriptor: WorkflowSkillGeneratorDescriptor
    options: dict[str, Any]
    files: tuple[GeneratedSkillFile, ...]
    warnings: tuple[str, ...] = ()

    def import_source(self, *, name: str) -> dict[str, Any]:
        return {
            "kind": "files",
            "name": name,
            "files": [file.to_payload() for file in self.files],
        }


class WorkflowSkillGenerator(Protocol):
    descriptor: WorkflowSkillGeneratorDescriptor

    def normalize_options(self, options: object) -> dict[str, Any]: ...

    def generate(
        self,
        context: WorkflowSkillGeneratorContext,
        options: object,
    ) -> WorkflowSkillGeneratorResult: ...


def normalize_empty_options(generator_id: str, options: object) -> dict[str, Any]:
    if not isinstance(options, dict):
        raise InvariantError(f"Workflow Skill Generator options must be an object: {generator_id}")
    if options:
        keys = ", ".join(sorted(str(key) for key in options))
        raise InvariantError(f"Workflow Skill Generator does not support options: {generator_id} ({keys})")
    return {}


def generated_text_file(path: str, content: str) -> GeneratedSkillFile:
    normalized = content.replace("\r\n", "\n").replace("\r", "\n").rstrip() + "\n"
    return GeneratedSkillFile(path=path, content_text=normalized)
