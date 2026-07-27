from __future__ import annotations

from collections.abc import Iterable

from skillhub.models.errors import InvariantError

from .contracts import (
    WorkflowSkillGenerator,
    WorkflowSkillGeneratorContext,
    WorkflowSkillGeneratorDescriptor,
    WorkflowSkillGeneratorResult,
)


class WorkflowSkillGeneratorRegistry:
    def __init__(self, generators: Iterable[WorkflowSkillGenerator]) -> None:
        registered = tuple(generators)
        by_id: dict[str, WorkflowSkillGenerator] = {}
        for generator in registered:
            descriptor = generator.descriptor
            if descriptor.id in by_id:
                raise InvariantError(f"Duplicate Workflow Skill Generator ID: {descriptor.id}")
            by_id[descriptor.id] = generator
        defaults = [generator for generator in registered if generator.descriptor.default]
        if len(defaults) != 1:
            raise InvariantError("Workflow Skill Generator registry must declare exactly one default Generator.")
        self._generators = registered
        self._by_id = by_id
        self._default = defaults[0]

    @property
    def descriptors(self) -> tuple[WorkflowSkillGeneratorDescriptor, ...]:
        return tuple(generator.descriptor for generator in self._generators)

    @property
    def default_descriptor(self) -> WorkflowSkillGeneratorDescriptor:
        return self._default.descriptor

    def get(self, generator_id: str) -> WorkflowSkillGenerator:
        try:
            return self._by_id[generator_id]
        except KeyError as exc:
            raise InvariantError(f"Unknown Workflow Skill Generator: {generator_id}") from exc

    def normalize_options(self, generator_id: str, options: object) -> dict:
        return self.get(generator_id).normalize_options(options)

    def generate(
        self,
        *,
        generator_id: str,
        context: WorkflowSkillGeneratorContext,
        options: object,
    ) -> WorkflowSkillGeneratorResult:
        return self.get(generator_id).generate(context, options)
