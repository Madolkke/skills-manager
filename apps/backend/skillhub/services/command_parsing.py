"""系统命令选择、可终止 TTP 解析与输出诊断编排。"""
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from skillhub.models.errors import CommandParseError
from skillhub.models.rules.command_parsing import command_identity, select_command, validate_result
from skillhub.models.store import SkillHubStore
from skillhub.services.base import ServiceBase

ECHO_MAX_BYTES = 1024 * 1024
PARSE_TIMEOUT_SECONDS = 5


def run_parser(template: str, echo: str, *, timeout: float = PARSE_TIMEOUT_SECONDS) -> object:
    """限制整个解析子进程的时间；超时杀死并 wait，不留下后台计算。"""
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(Path(__file__).resolve().parents[2])
    environment["PYTHONIOENCODING"] = "utf-8"
    try:
        process = subprocess.Popen(
            [sys.executable, "-m", "skillhub.services.ttp_worker"], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, encoding="utf-8", env=environment,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
    except OSError as exc:
        raise CommandParseError("TTP_PARSE_FAILED", "TTP 解析进程无法启动。", 400) from exc
    try:
        output, _ = process.communicate(json.dumps({"template": template, "echo": echo}), timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        process.kill()
        process.communicate()
        raise CommandParseError("TTP_PARSE_TIMEOUT", "TTP 解析超过 5 秒，已终止。", 504) from exc
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
    try:
        response = json.loads(output)
        if process.returncode or not isinstance(response, dict):
            raise ValueError
        if "code" in response:
            raise CommandParseError(response["code"], response["detail"], 400)
        return response["result"]
    except (ValueError, KeyError) as exc:
        raise CommandParseError("TTP_PARSE_FAILED", "TTP 解析进程未返回有效结果。", 400) from exc


class CommandParsingService(ServiceBase[SkillHubStore]):
    """查询与解析均不产生数据库写入。"""

    def parse(self, *, command: str, echo: str, actor: str) -> dict[str, Any]:
        """使用最佳系统规则解析回显，类型不一致只返回提醒。"""
        if len(echo.encode("utf-8")) > ECHO_MAX_BYTES:
            raise CommandParseError("ECHO_TOO_LARGE", "echo 的 UTF-8 内容不能超过 1 MiB。", 413)
        entries = self.store.search_command_library(query=command, actor=actor, include_system=True, include_user=False,
                                                   include_disabled=False, partial=False, prefix=False)
        entry = select_command(entries)
        result = run_parser(entry["ttp"], echo)
        return {"command": command_identity(entry), "result": result, "validation": validate_result(result, entry["outputSchema"])}
