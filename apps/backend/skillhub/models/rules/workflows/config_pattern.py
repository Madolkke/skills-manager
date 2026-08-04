from __future__ import annotations

import keyword
import re
from dataclasses import dataclass

_DICT_METHOD_NAMES = frozenset(
    {"clear", "copy", "fromkeys", "get", "items", "keys", "pop", "popitem", "setdefault", "update", "values"}
)
_DEFAULT_CAPTURE_PATTERN = r"\S+"


@dataclass(frozen=True)
class ConfigPatternError(ValueError):
    code: str
    message: str
    offset: int = 0

    def __str__(self) -> str:
        return self.message


@dataclass(frozen=True)
class ParsedConfigPattern:
    names: tuple[str, ...]
    regex: str


def is_config_identifier(value: str) -> bool:
    """Return whether a name can be safely exposed through config dot access."""
    return bool(
        value
        and value.isidentifier()
        and not keyword.iskeyword(value)
        and not value.startswith("_")
        and value not in _DICT_METHOD_NAMES
    )


def parse_config_pattern(pattern: str) -> ParsedConfigPattern:
    """Parse a mixed literal/capture template and validate its Python regex."""
    if "\n" in pattern or "\r" in pattern:
        raise ConfigPatternError("CONFIG_COMMAND_PATTERN_MULTILINE", "配置命令匹配模板必须为单行。")
    if not pattern.strip():
        raise ConfigPatternError("CONFIG_COMMAND_PATTERN_INVALID", "配置命令匹配模板不能为空。")

    parts: list[str] = []
    names: list[str] = []
    index = 0
    while index < len(pattern):
        character = pattern[index]
        if character == "<":
            end = _find_capture_end(pattern, index + 1)
            if end < 0:
                raise ConfigPatternError("CONFIG_COMMAND_PATTERN_INVALID", "配置命令匹配模板存在未闭合的尖括号。", index)
            body = pattern[index + 1 : end]
            name, expression = _split_capture(body, index)
            _validate_name(name, "CONFIG_CAPTURE_NAME_INVALID", "捕获名称", index)
            if name in names:
                raise ConfigPatternError("CONFIG_CAPTURE_NAME_DUPLICATE", f"捕获名称“{name}”在同一行中重复。", index)
            if not expression:
                expression = _DEFAULT_CAPTURE_PATTERN
            try:
                re.compile(f"(?P<{name}>{expression})")
            except re.error as exc:
                raise ConfigPatternError("CONFIG_COMMAND_PATTERN_INVALID", f"捕获“{name}”的正则无效：{exc}。", index) from exc
            names.append(name)
            parts.append(f"(?P<{name}>{expression})")
            index = end + 1
            continue
        literal, next_index = _read_literal(pattern, index)
        parts.append(literal)
        index = next_index

    expression = "^" + "".join(parts).strip() + "$"
    try:
        re.compile(expression)
    except re.error as exc:
        raise ConfigPatternError("CONFIG_COMMAND_PATTERN_INVALID", f"配置命令匹配模板的正则无效：{exc}。") from exc
    return ParsedConfigPattern(tuple(names), expression)


def _find_capture_end(pattern: str, start: int) -> int:
    escaped = False
    for index in range(start, len(pattern)):
        character = pattern[index]
        if escaped:
            escaped = False
        elif character == "\\":
            escaped = True
        elif character == ">":
            return index
    return -1


def _split_capture(body: str, offset: int) -> tuple[str, str]:
    name, separator, expression = body.partition(":")
    if not name.strip():
        raise ConfigPatternError("CONFIG_COMMAND_PATTERN_INVALID", "尖括号捕获必须包含名称。", offset)
    if name != name.strip():
        raise ConfigPatternError("CONFIG_COMMAND_PATTERN_INVALID", "捕获名称前后不能包含空白。", offset)
    if separator and not expression:
        raise ConfigPatternError("CONFIG_COMMAND_PATTERN_INVALID", "捕获正则不能为空。", offset)
    return name, expression if separator else _DEFAULT_CAPTURE_PATTERN


def _validate_name(name: str, code: str, label: str, offset: int) -> None:
    if not name.isidentifier() or keyword.iskeyword(name) or name.startswith("_"):
        raise ConfigPatternError(code, f"{label}“{name}”必须是非关键字且不以下划线开头的 Python 标识符。", offset)
    if name in _DICT_METHOD_NAMES:
        raise ConfigPatternError("CONFIG_COMMAND_NAME_RESERVED", f"{label}“{name}”与对象方法冲突。", offset)


def validate_config_name(name: str, *, label: str = "命令名称") -> None:
    """Validate a command or capture map name outside a pattern."""
    _validate_name(name, "CONFIG_COMMAND_NAME_INVALID", label, 0)


def _read_literal(pattern: str, start: int) -> tuple[str, int]:
    index = start
    literal: list[str] = []
    while index < len(pattern) and pattern[index] != "<":
        character = pattern[index]
        if character == "\\" and index + 1 < len(pattern) and pattern[index + 1] in "<>\\":
            literal.append(re.escape(pattern[index + 1]))
            index += 2
            continue
        if character.isspace():
            while index < len(pattern) and pattern[index].isspace():
                index += 1
            if not literal or literal[-1] != r"\s+":
                literal.append(r"\s+")
            continue
        literal.append(re.escape(character))
        index += 1
    return "".join(literal), index


__all__ = ["ConfigPatternError", "ParsedConfigPattern", "is_config_identifier", "parse_config_pattern", "validate_config_name"]
