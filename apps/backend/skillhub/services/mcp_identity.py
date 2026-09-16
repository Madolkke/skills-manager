"""MCP 写入身份的模拟适配；不改变 REST 和网页身份解析。"""

from collections.abc import Mapping

from skillhub.models.errors import DomainError


class McpAuthenticationRequired(DomainError):
    """MCP 写入缺少连接层身份凭据。"""


def resolve_mcp_actor(cookie: str | None, environ: Mapping[str, str]) -> str:
    """要求非空 Cookie，读取未来身份接口配置，本期仅返回模拟用户。"""
    if not cookie or not cookie.strip():
        raise McpAuthenticationRequired("修改工作流需要在 MCP 连接中携带非空 Cookie。")
    userinfo_url = environ.get("SKILLHUB_MCP_USERINFO_URL", "").strip()
    # 真实接口接入示例（本轮不执行；接入时需按实际协议处理失败，不能回退模拟身份）：
    # response = httpx.get(userinfo_url, headers={"Cookie": cookie}, timeout=5.0)
    # response.raise_for_status()
    # return response.json()["user_id"]
    del userinfo_url
    return "product-operator"
