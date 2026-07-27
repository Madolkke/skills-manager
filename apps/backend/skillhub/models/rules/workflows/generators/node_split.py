from __future__ import annotations

from skillhub.models.errors import InvariantError
from skillhub.models.rules.skill_imports import MAX_BUNDLE_BYTES, MAX_BUNDLE_FILES

from .contracts import (
    EMPTY_OPTIONS_SCHEMA,
    WorkflowSkillGeneratorContext,
    WorkflowSkillGeneratorDescriptor,
    WorkflowSkillGeneratorResult,
    generated_text_file,
    normalize_empty_options,
)
from .documents import (
    collection_reference_path,
    node_reference_path,
    render_collection_reference,
    render_entry,
    render_node_index,
    render_node_reference,
)


class NodeSplitWorkflowSkillGenerator:
    descriptor = WorkflowSkillGeneratorDescriptor(
        id="builtin.node-split",
        version="1.0.0",
        label="按节点拆分",
        default=False,
        options_schema=EMPTY_OPTIONS_SCHEMA,
    )

    def normalize_options(self, options: object) -> dict:
        return normalize_empty_options(self.descriptor.id, options)

    def generate(self, context: WorkflowSkillGeneratorContext, options: object) -> WorkflowSkillGeneratorResult:
        normalized = self.normalize_options(options)
        nodes = context.document["workflow"]["nodes"]
        definitions = context.document.get("collectionSnapshots", [])
        file_count = 2 + len(nodes) + len(definitions)
        if file_count > MAX_BUNDLE_FILES:
            raise InvariantError(
                f"Node-split Workflow Skill would generate {file_count} files, exceeding the {MAX_BUNDLE_FILES}-file Bundle limit; "
                "use builtin.three-file instead."
            )
        files = [
            generated_text_file(
                "SKILL.md",
                render_entry(
                    slug=context.slug,
                    document=context.document,
                    reference_path="references/index.md",
                    split_nodes=True,
                ),
            ),
            generated_text_file("references/index.md", render_node_index(context.document)),
        ]
        files.extend(
            generated_text_file(node_reference_path(node), render_node_reference(context.document, node)) for node in nodes
        )
        files.extend(
            generated_text_file(collection_reference_path(definition), render_collection_reference(definition))
            for definition in definitions
        )
        generated_files = tuple(files)
        total_size = sum(len(file.content_text.encode("utf-8")) for file in generated_files)
        if total_size > MAX_BUNDLE_BYTES:
            raise InvariantError(
                f"Node-split Workflow Skill would generate {total_size} bytes, exceeding the {MAX_BUNDLE_BYTES}-byte Bundle limit; "
                "use builtin.three-file instead."
            )
        return WorkflowSkillGeneratorResult(descriptor=self.descriptor, options=normalized, files=generated_files)
