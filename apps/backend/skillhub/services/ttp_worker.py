"""一次性 TTP 子进程入口；标准输入输出仅传递 JSON。"""
import contextlib
import json
import logging
import os
import sys

from skillhub.models.errors import CommandParseError
from skillhub.models.rules.ttp_template import literal_attributes, validate_template


class ParseLogHandler(logging.Handler):
    """仅保留错误标记，绝不保存或输出 TTP 的原始日志内容。"""

    failed = False

    def emit(self, record: logging.LogRecord) -> None:
        """将被 TTP 吞掉的错误转换为调用失败。"""
        if record.levelno >= logging.WARNING:
            self.failed = True


def parse_text(template: str, echo: str) -> object:
    """在独立进程内解析，强制模板与回显都作为内存文本。"""
    from ttp import ttp

    template = validate_template(template)
    handler = ParseLogHandler()
    logger = logging.getLogger("ttp")
    logger.handlers = [handler]
    logger.propagate = False
    logger.setLevel(logging.WARNING)
    parser = ttp()
    # TTP 0.10.1 默认 loader 会识别路径；本适配明确禁用该隐式能力。
    parser._ttp_["utils"]["load_files"] = lambda path, **kwargs: [("text_data", path)]
    parser._ttp_["utils"]["get_attributes"] = literal_attributes
    parser.add_template(template)
    parser.add_input(echo)
    parser.parse(one=True)
    if handler.failed:
        raise CommandParseError("TTP_PARSE_FAILED", "TTP 编译或解析失败，请检查模板与回显。", 400)
    results = parser.result(structure="list")
    if len(results) != 1 or len(results[0]) != 1:
        raise CommandParseError("TTP_PARSE_FAILED", "TTP 返回了不支持的模板或输入结果结构。", 400)
    return results[0][0]


def main() -> None:
    """捕获库异常和 SystemExit，进程错误只返回固定中文说明。"""
    try:
        payload = json.load(sys.stdin)
        with open(os.devnull, "w") as sink, contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
            result = parse_text(payload["template"], payload["echo"])
        response = json.dumps({"result": result}, ensure_ascii=False, allow_nan=False)
    except CommandParseError as exc:
        response = json.dumps({"code": exc.code, "detail": str(exc)}, ensure_ascii=False)
    except BaseException:
        response = json.dumps({"code": "TTP_PARSE_FAILED", "detail": "TTP 编译、解析或 JSON 序列化失败。"}, ensure_ascii=False)
    sys.stdout.write(response)


if __name__ == "__main__":
    main()
