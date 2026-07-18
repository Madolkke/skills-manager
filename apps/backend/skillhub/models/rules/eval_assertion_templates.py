from __future__ import annotations

from difflib import SequenceMatcher
from pathlib import Path, PurePosixPath
from typing import Any

from skillhub.models.errors import InvariantError
from skillhub.models.rules.assertion_base import AssertionContext, AssertionParam, AssertionResult, AssertionTemplate


class AgentOutputExactTemplate(AssertionTemplate):
    id = "agent_output_exact"
    name = "Agent 输出严格等于"
    description = "Agent 本轮输出必须与期望文本完全一致。"
    category = "Agent 输出"
    params = (AssertionParam("expected", "期望文本", "textarea", placeholder="填写完整期望输出"),)

    def evaluate(self, context: AssertionContext, params: dict[str, Any]) -> AssertionResult:
        expected = str(params["expected"])
        actual = context.agent_output
        passed = actual.strip() == expected.strip()
        return AssertionResult(passed, actual, "输出完全一致。" if passed else "输出与期望文本不一致。", {"expected": expected})


class AgentOutputContainsTemplate(AssertionTemplate):
    id = "agent_output_contains"
    name = "Agent 输出包含文本"
    description = "Agent 本轮输出必须包含指定文本。"
    category = "Agent 输出"
    params = (AssertionParam("text", "必须包含", "textarea", placeholder="填写必须出现的关键文本"),)

    def evaluate(self, context: AssertionContext, params: dict[str, Any]) -> AssertionResult:
        needle = str(params["text"])
        passed = needle in context.agent_output
        return AssertionResult(passed, context.agent_output, "输出包含指定文本。" if passed else "输出未包含指定文本。", {"text": needle})


class AgentOutputSimilarityTemplate(AssertionTemplate):
    id = "agent_output_similarity"
    name = "Agent 输出相似度不低于阈值"
    description = "用字符串相似度比较 Agent 输出和期望文本。"
    category = "Agent 输出"
    params = (
        AssertionParam("expected", "期望文本", "textarea", placeholder="填写用于比较的文本"),
        AssertionParam("threshold", "相似度阈值", "number", default=0.85, min=0, max=1, help="0 到 1 之间，越高越严格。"),
    )

    def evaluate(self, context: AssertionContext, params: dict[str, Any]) -> AssertionResult:
        expected = str(params["expected"])
        threshold = _threshold(params.get("threshold"))
        ratio = _similarity(context.agent_output, expected)
        passed = ratio >= threshold
        return AssertionResult(
            passed,
            context.agent_output,
            f"相似度 {ratio:.2f}，阈值 {threshold:.2f}。",
            {"expected": expected, "threshold": threshold, "similarity": ratio},
        )


class AgentOutputSemanticTemplate(AgentOutputSimilarityTemplate):
    id = "agent_output_semantic"
    name = "Agent 输出语义满足"
    description = "初版使用本地相似度近似语义判定；后续可替换为 LLM Judge。"
    category = "语义判定"


class FileExistsTemplate(AssertionTemplate):
    id = "file_exists"
    name = "路径下存在文件名"
    description = "检查工作目录指定路径下是否存在某个文件。"
    category = "工作目录文件"
    params = (
        AssertionParam("directory", "目录", "text", default=".", placeholder="例如：src"),
        AssertionParam("filename", "文件名", "text", placeholder="例如：result.txt"),
    )

    def evaluate(self, context: AssertionContext, params: dict[str, Any]) -> AssertionResult:
        path = safe_workdir_path(context.workdir, str(params["directory"]), str(params["filename"]))
        passed = path.is_file()
        rel = _relative(context.workdir, path)
        return AssertionResult(passed, rel, "文件存在。" if passed else "未找到指定文件。", {"path": rel})


class NewFileTemplate(FileExistsTemplate):
    id = "file_created"
    name = "路径下新增文件名"
    description = "检查当前步骤执行后是否新增了指定文件。"
    category = "工作目录文件"

    def evaluate(self, context: AssertionContext, params: dict[str, Any]) -> AssertionResult:
        path = safe_workdir_path(context.workdir, str(params["directory"]), str(params["filename"]))
        rel = _relative(context.workdir, path)
        passed = rel not in context.before_snapshot and rel in context.after_snapshot and path.is_file()
        return AssertionResult(passed, rel, "文件已新增。" if passed else "指定文件不是本步骤新增文件。", {"path": rel})


class FileContentExactTemplate(AssertionTemplate):
    id = "file_content_exact"
    name = "路径下存在文件内容严格等于"
    description = "指定文件必须存在，且内容与期望文本完全一致。"
    category = "工作目录文件"
    params = (
        AssertionParam("path", "文件路径", "text", placeholder="例如：docs/output.md"),
        AssertionParam("expected", "期望内容", "textarea"),
    )

    def evaluate(self, context: AssertionContext, params: dict[str, Any]) -> AssertionResult:
        path = safe_workdir_path(context.workdir, str(params["path"]))
        actual = _read_file_or_result(context, path)
        if isinstance(actual, AssertionResult):
            return actual
        expected = str(params["expected"])
        passed = actual.strip() == expected.strip()
        return AssertionResult(passed, actual, "文件内容完全一致。" if passed else "文件内容与期望不一致。", {"path": _relative(context.workdir, path)})


class FileContentContainsTemplate(AssertionTemplate):
    id = "file_content_contains"
    name = "路径下文件内容包含文本"
    description = "指定文件必须存在，且内容包含指定文本。"
    category = "工作目录文件"
    params = (
        AssertionParam("path", "文件路径", "text", placeholder="例如：docs/output.md"),
        AssertionParam("text", "必须包含", "textarea"),
    )

    def evaluate(self, context: AssertionContext, params: dict[str, Any]) -> AssertionResult:
        path = safe_workdir_path(context.workdir, str(params["path"]))
        actual = _read_file_or_result(context, path)
        if isinstance(actual, AssertionResult):
            return actual
        needle = str(params["text"])
        passed = needle in actual
        return AssertionResult(passed, actual, "文件内容包含指定文本。" if passed else "文件内容未包含指定文本。", {"path": _relative(context.workdir, path), "text": needle})


class FileContentSimilarityTemplate(FileContentExactTemplate):
    id = "file_content_similarity"
    name = "路径下文件内容相似度不低于阈值"
    description = "指定文件内容必须与期望文本达到相似度阈值。"
    category = "工作目录文件"
    params = (
        AssertionParam("path", "文件路径", "text", placeholder="例如：docs/output.md"),
        AssertionParam("expected", "期望内容", "textarea"),
        AssertionParam("threshold", "相似度阈值", "number", default=0.85, min=0, max=1),
    )

    def evaluate(self, context: AssertionContext, params: dict[str, Any]) -> AssertionResult:
        path = safe_workdir_path(context.workdir, str(params["path"]))
        actual = _read_file_or_result(context, path)
        if isinstance(actual, AssertionResult):
            return actual
        expected = str(params["expected"])
        threshold = _threshold(params.get("threshold"))
        ratio = _similarity(actual, expected)
        return AssertionResult(
            ratio >= threshold,
            actual,
            f"相似度 {ratio:.2f}，阈值 {threshold:.2f}。",
            {"path": _relative(context.workdir, path), "expected": expected, "threshold": threshold, "similarity": ratio},
        )


def _opencode_process_templates() -> tuple[AssertionTemplate, ...]:
    from skillhub.models.rules.opencode_assertion_templates import opencode_process_templates

    return opencode_process_templates()


TEMPLATES: tuple[AssertionTemplate, ...] = (
    AgentOutputSemanticTemplate(),
    AgentOutputExactTemplate(),
    AgentOutputContainsTemplate(),
    AgentOutputSimilarityTemplate(),
    FileExistsTemplate(),
    NewFileTemplate(),
    FileContentExactTemplate(),
    FileContentContainsTemplate(),
    FileContentSimilarityTemplate(),
    *_opencode_process_templates(),
)


def list_assertion_templates() -> list[dict[str, Any]]:
    return [template.definition() for template in TEMPLATES]


def assertion_template(template_id: str) -> AssertionTemplate:
    for template in TEMPLATES:
        if template.id == template_id:
            return template
    raise InvariantError(f"Unknown assertion template: {template_id}")


def normalize_assertion_step(step: dict[str, Any], index: int) -> dict[str, Any]:
    input_text = str(step.get("input") or "").strip()
    if not input_text:
        raise InvariantError("Eval case step input is required.")
    assertions = step.get("assertions")
    raw_assertions = assertions if isinstance(assertions, list) and assertions else [_legacy_assertion(step)]
    return {
        "id": str(step.get("id") or f"step-{index + 1}"),
        "title": str(step.get("title") or f"步骤 {index + 1}").strip() or f"步骤 {index + 1}",
        "input": input_text,
        "assertions": [normalize_step_assertion(assertion, assertion_index) for assertion_index, assertion in enumerate(raw_assertions)],
    }


def normalize_step_assertion(assertion: dict[str, Any], index: int) -> dict[str, Any]:
    template_id = str(assertion.get("assertion_template_id") or "agent_output_semantic")
    template = assertion_template(template_id)
    return {
        "id": str(assertion.get("id") or f"assertion-{index + 1}"),
        "assertion_template_id": template_id,
        "assertion_params": template.normalize_params(assertion.get("assertion_params") if isinstance(assertion.get("assertion_params"), dict) else {}),
    }


def _legacy_assertion(step: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": "assertion-1",
        "assertion_template_id": step.get("assertion_template_id") or "agent_output_semantic",
        "assertion_params": step.get("assertion_params") if isinstance(step.get("assertion_params"), dict) else {},
    }


def safe_workdir_path(workdir: Path, *parts: str) -> Path:
    joined = "/".join(part for part in parts if part)
    _reject_unsafe_path_text(joined)
    relative = PurePosixPath(joined or ".")
    if relative.is_absolute() or any(part == ".." or _is_windows_drive(part) for part in relative.parts):
        raise InvariantError(f"Unsafe workdir path: {joined}")
    root = workdir.resolve()
    target = (root / Path(*[part for part in relative.parts if part not in {"", "."}])).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise InvariantError(f"Unsafe workdir path: {joined}") from exc
    return target


def _similarity(left: str, right: str) -> float:
    return SequenceMatcher(None, left.strip(), right.strip()).ratio()


def _threshold(value: Any) -> float:
    try:
        threshold = float(value)
    except (TypeError, ValueError) as exc:
        raise InvariantError("Similarity threshold must be a number.") from exc
    if threshold < 0 or threshold > 1:
        raise InvariantError("Similarity threshold must be between 0 and 1.")
    return threshold


def _read_file_or_result(context: AssertionContext, path: Path) -> str | AssertionResult:
    if not path.is_file():
        return AssertionResult(False, "", "文件不存在。", {"path": _relative(context.workdir, path)})
    return path.read_text(encoding="utf-8")


def _relative(workdir: Path, path: Path) -> str:
    return path.resolve().relative_to(workdir.resolve()).as_posix()


def _reject_unsafe_path_text(path: str) -> None:
    if "\\" in path or "\x00" in path:
        raise InvariantError(f"Unsafe workdir path: {path}")


def _is_windows_drive(part: str) -> bool:
    return len(part) == 2 and part[1] == ":"
