from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EvalPromptTemplate:
    id: str
    name: str
    description: str
    body: str


PROMPT_TEMPLATES: tuple[EvalPromptTemplate, ...] = (
    EvalPromptTemplate(
        id="standard_pass_fail",
        name="通用判定",
        description="根据 input 和 expected output 执行 Skill，并判断是否通过。",
        body=(
            "你正在运行一个 SkillHub Eval case。\n"
            "Skill 文件位于：{skill_file}\n"
            "工作目录位于：{workdir}\n"
            "请阅读 Skill 指令，基于下面的 input 产出 actual_output，并与 expected output 比较。\n\n"
            "Input:\n{input}\n\n"
            "Expected output:\n{expected_output}\n\n"
            "必须把结果写入 JSON 文件：{result_json_path}"
        ),
    ),
    EvalPromptTemplate(
        id="file_workspace_task",
        name="工作目录文件任务",
        description="适合 zip 附件会解压到工作目录的 case。",
        body=(
            "你正在工作目录 {workdir} 中执行 Eval case。\n"
            "Skill 文件位于：{skill_file}\n"
            "压缩包中的文件已经复制到工作目录。请检查这些文件并完成 input 要求。\n\n"
            "Input:\n{input}\n\n"
            "Expected output:\n{expected_output}\n\n"
            "必须把结果写入 JSON 文件：{result_json_path}"
        ),
    ),
    EvalPromptTemplate(
        id="exact_match",
        name="严格文本匹配",
        description="适合期望输出需要严格一致的 case。",
        body=(
            "按 Skill 指令处理 input，actual_output 必须尽量与 expected output 完全一致。\n"
            "Skill 文件位于：{skill_file}\n"
            "工作目录位于：{workdir}\n\n"
            "Input:\n{input}\n\n"
            "Expected output:\n{expected_output}\n\n"
            "必须把结果写入 JSON 文件：{result_json_path}"
        ),
    ),
    EvalPromptTemplate(
        id="semantic_judge",
        name="语义判定",
        description="适合自然语言输出，只要求语义满足预期。",
        body=(
            "按 Skill 指令处理 input，判断 actual_output 是否在语义上满足 expected output。\n"
            "不要要求措辞完全一致，但必须覆盖关键事实和约束。\n"
            "Skill 文件位于：{skill_file}\n"
            "工作目录位于：{workdir}\n\n"
            "Input:\n{input}\n\n"
            "Expected output:\n{expected_output}\n\n"
            "必须把结果写入 JSON 文件：{result_json_path}"
        ),
    ),
    EvalPromptTemplate(
        id="custom",
        name="自定义 Prompt",
        description="使用 case 自己填写的 Prompt。",
        body="",
    ),
)


def list_eval_prompt_templates() -> list[dict[str, str]]:
    return [template.__dict__.copy() for template in PROMPT_TEMPLATES]


def prompt_template_body(template_id: str) -> str:
    for template in PROMPT_TEMPLATES:
        if template.id == template_id:
            return template.body
    return PROMPT_TEMPLATES[0].body
