from __future__ import annotations

import keyword
from dataclasses import dataclass


@dataclass(frozen=True)
class CliCommandParameters:
    names: tuple[str, ...]
    error: str | None = None


def parse_cli_command_parameters(command: str) -> CliCommandParameters:
    """Parse angle-bracket parameters without interpreting the command itself."""
    names: list[str] = []
    index = 0
    while index < len(command):
        character = command[index]
        if character == ">":
            return CliCommandParameters(tuple(names), "采集命令包含未配对的尖括号。")
        if character != "<":
            index += 1
            continue
        end = command.find(">", index + 1)
        if end < 0:
            return CliCommandParameters(tuple(names), "采集命令包含未闭合的参数。")
        name = command[index + 1 : end]
        if not name or "<" in name:
            return CliCommandParameters(tuple(names), "采集命令参数必须使用 <name> 格式。")
        if not name.isidentifier() or keyword.iskeyword(name):
            return CliCommandParameters(tuple(names), f"采集命令参数“{name}”必须是合法的 Python 标识符。")
        if name not in names:
            names.append(name)
        index = end + 1
    return CliCommandParameters(tuple(names))


__all__ = ["CliCommandParameters", "parse_cli_command_parameters"]
