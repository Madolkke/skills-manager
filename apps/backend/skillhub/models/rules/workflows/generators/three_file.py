from __future__ import annotations

from .contracts import (
    EMPTY_OPTIONS_SCHEMA,
    WorkflowSkillGeneratorContext,
    WorkflowSkillGeneratorDescriptor,
    WorkflowSkillGeneratorResult,
    generated_text_file,
    normalize_empty_options,
)
from .documents import render_collections_reference, render_entry, render_workflow_reference


class ThreeFileWorkflowSkillGenerator:
    descriptor = WorkflowSkillGeneratorDescriptor(
        id="builtin.three-file",
        version="2.0.0",
        label="固定三文件",
        default=True,
        options_schema=EMPTY_OPTIONS_SCHEMA,
    )

    def normalize_options(self, options: object) -> dict:
        return normalize_empty_options(self.descriptor.id, options)

    def generate(self, context: WorkflowSkillGeneratorContext, options: object) -> WorkflowSkillGeneratorResult:
        normalized = self.normalize_options(options)
        files = (
            generated_text_file(
                "SKILL.md",
                render_entry(
                    slug=context.slug,
                    document=context.document,
                    reference_path="references/workflow.md",
                    split_nodes=False,
                ),
            ),
            generated_text_file("references/workflow.md", render_workflow_reference(context.document)),
            generated_text_file("references/collections.md", render_collections_reference(context.document)),
        )
        return WorkflowSkillGeneratorResult(descriptor=self.descriptor, options=normalized, files=files)
