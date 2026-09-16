"""MCP HTTP 部署参数，默认沿用本机 Host 和 Origin 范围。"""

from collections.abc import Mapping

from mcp.server.transport_security import TransportSecuritySettings


def transport_security(environ: Mapping[str, str]) -> TransportSecuritySettings:
    """逗号分隔的部署域名附加到本机列表，供反向代理和远程客户端使用。"""
    hosts = ["127.0.0.1:*", "localhost:*", "[::1]:*"]
    origins = ["http://127.0.0.1:*", "http://localhost:*", "http://[::1]:*"]
    hosts.extend(_values(environ.get("SKILLHUB_MCP_ALLOWED_HOSTS", "")))
    origins.extend(_values(environ.get("SKILLHUB_MCP_ALLOWED_ORIGINS", "")))
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=list(dict.fromkeys(hosts)), allowed_origins=list(dict.fromkeys(origins)),
    )


def _values(raw: str) -> list[str]:
    """忽略空条目，保留 SDK 支持的显式端口或通配端口格式。"""
    return [item.strip().rstrip("/") for item in raw.split(",") if item.strip()]
