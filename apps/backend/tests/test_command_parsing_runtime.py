"""真实 TTP 子进程解析、隔离及进程回收。"""
import subprocess

import pytest

from skillhub.models.errors import CommandParseError
from skillhub.services.command_parsing import run_parser

TEMPLATE = '<group name="interfaces*">\nInterface {{ name }} is {{ state }}\n packets {{ packets | to_int }}\n</group>'


def test_objects_arrays_crlf_and_unicode():
    assert run_parser(TEMPLATE, 'Interface eth0 is up\r\n packets 42\r\nInterface 网口 is down\r\n packets 0\r\n') == {
        "interfaces": [{"name": "eth0", "state": "up", "packets": 42}, {"name": "网口", "state": "down", "packets": 0}]}
    assert run_parser('Version {{ version }}', 'Version 1.2\n') == {"version": "1.2"}
    assert run_parser('{{ name }} {{ state }}', 'eth0 up\neth1 down\n') == [
        {"name": "eth0", "state": "up"}, {"name": "eth1", "state": "down"}]


def test_nested_arrays_and_empty_output():
    template = '<group name="peers*">\nPeer {{ address }}\n<group name="families*">\n family {{ name }}\n<group name="prefixes">\n  received {{ count | to_int }}\n</group>\n</group>\n</group>'
    assert run_parser(template, 'Peer 10.0.0.1\n family ipv4\n  received 12\n') == {
        "peers": [{"address": "10.0.0.1", "families": [{"name": "ipv4", "prefixes": {"count": 12}}]}]}
    assert run_parser(TEMPLATE, '') == {}
    assert run_parser(TEMPLATE, 'nothing matches\n') == {}


def test_paths_remain_text(tmp_path):
    path = tmp_path / "echo.txt"
    path.write_text("Interface SECRET is up\n", encoding="utf-8")
    assert run_parser('{{ value | ORPHRASE }}', str(path)) == {"value": str(path)}
    assert run_parser('{{ value }}', 'ttp://secret') == {"value": "ttp://secret"}
    with pytest.raises(CommandParseError, match="模板无效"):
        run_parser(str(path), '')


@pytest.mark.parametrize("template,echo", [
    ('{{ value | to_int }}', 'secret'), ('{{ value | re("[") }}', 'text'),
    ('{{ value | to_float }}', 'nan'), ('{{ value | nonexistent }}', 'text'),
])
def test_errors_not_silent_success(template, echo, caplog):
    with pytest.raises(CommandParseError) as exc:
        run_parser(template, echo)
    assert exc.value.code in {"TTP_TEMPLATE_INVALID", "TTP_PARSE_FAILED"}
    assert 'secret' not in str(exc.value) + caplog.text


def test_timeout_reaps_process_and_next_request_succeeds(monkeypatch):
    processes = []
    original = subprocess.Popen

    def track(*args, **kwargs):
        """记录实际子进程以核对终止后的状态。"""
        process = original(*args, **kwargs)
        processes.append(process)
        return process

    monkeypatch.setattr(subprocess, "Popen", track)
    with pytest.raises(CommandParseError) as exc:
        run_parser(TEMPLATE, 'Interface eth0 is up', timeout=0.001)
    assert exc.value.code == "TTP_PARSE_TIMEOUT"
    assert processes[0].poll() is not None
    assert run_parser('Version {{ version }}', 'Version 2') == {"version": "2"}


def test_process_start_failure_has_public_error(monkeypatch):
    def fail(*args, **kwargs):
        """模拟系统无法创建子进程，不泄露操作系统异常。"""
        raise OSError("internal path")

    monkeypatch.setattr(subprocess, "Popen", fail)
    with pytest.raises(CommandParseError) as exc:
        run_parser(TEMPLATE, "")
    assert exc.value.code == "TTP_PARSE_FAILED"
    assert "internal path" not in str(exc.value)
