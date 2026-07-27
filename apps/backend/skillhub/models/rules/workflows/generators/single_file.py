from __future__ import annotations

from ..renderer import GENERATOR_VERSION, render_skill_markdown
from .contracts import (
    EMPTY_OPTIONS_SCHEMA,
    GeneratedSkillFile,
    WorkflowSkillGeneratorContext,
    WorkflowSkillGeneratorDescriptor,
    WorkflowSkillGeneratorResult,
    normalize_empty_options,
)


class SingleFileWorkflowSkillGenerator:
    descriptor = WorkflowSkillGeneratorDescriptor(
        id="builtin.single-file",
        version=GENERATOR_VERSION,
        label="单文件（兼容模式）",
        default=False,
        options_schema=EMPTY_OPTIONS_SCHEMA,
    )

    def normalize_options(self, options: object) -> dict:
        return normalize_empty_options(self.descriptor.id, options)

    def generate(self, context: WorkflowSkillGeneratorContext, options: object) -> WorkflowSkillGeneratorResult:
        normalized = self.normalize_options(options)
        markdown = render_skill_markdown(slug=context.slug, document=context.document)
        return WorkflowSkillGeneratorResult(
            descriptor=self.descriptor,
            options=normalized,
            files=(GeneratedSkillFile(path="SKILL.md", content_text=markdown),),
        )
