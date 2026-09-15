"""httpx AsyncClient 封装：连接池 + 超时，供各 MCP 工具复用。"""
from __future__ import annotations

import httpx

from . import server_config

_client: httpx.AsyncClient | None = None


def get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            base_url=server_config.ERP_BASE_URL,
            timeout=httpx.Timeout(10.0),
        )
    return _client
