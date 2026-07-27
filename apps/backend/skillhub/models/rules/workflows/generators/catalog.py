from __future__ import annotations

from .contracts import WorkflowSkillGeneratorContext, WorkflowSkillGeneratorDescriptor, WorkflowSkillGeneratorResult
from .node_split import NodeSplitWorkflowSkillGenerator
from .registry import WorkflowSkillGeneratorRegistry
from .single_file import SingleFileWorkflowSkillGenerator
from .three_file import ThreeFileWorkflowSkillGenerator

WORKFLOW_SKILL_GENERATORS = WorkflowSkillGeneratorRegistry(
    (
        SingleFileWorkflowSkillGenerator(),
        ThreeFileWorkflowSkillGenerator(),
        NodeSplitWorkflowSkillGenerator(),
    )
)
DEFAULT_WORKFLOW_SKILL_GENERATOR_ID = WORKFLOW_SKILL_GENERATORS.default_descriptor.id


def list_workflow_skill_generators() -> tuple[WorkflowSkillGeneratorDescriptor, ...]:
    return WORKFLOW_SKILL_GENERATORS.descriptors


def generate_workflow_skill(
    *,
    slug: str,
    document: dict,
    generator_id: str,
    generator_options: object,
) -> WorkflowSkillGeneratorResult:
    return WORKFLOW_SKILL_GENERATORS.generate(
        generator_id=generator_id,
        context=WorkflowSkillGeneratorContext(slug=slug, document=document),
        options=generator_options,
    )
