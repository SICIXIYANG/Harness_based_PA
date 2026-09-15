"""库存预警 MCP 工具。"""
from __future__ import annotations

import json

from mcp.server.mcpserver import MCPServer

from ..http_base import get_client


def register(server: MCPServer) -> None:
    @server.tool()
    async def inventory_warning() -> str:
        """查询库存预警：返回当前库存低于预警阈值的所有物料。"""
        resp = await get_client().get("/api/inventory/warning")
        resp.raise_for_status()
        return json.dumps(resp.json(), ensure_ascii=False)

    @server.tool()
    async def inventory_query(part_id: str) -> str:
        """查询单个物料的当前库存（数量、预警阈值、是否预警）。

        Args:
            part_id: 物料编号，例如 P003
        """
        resp = await get_client().get(f"/api/inventory/{part_id}")
        if resp.status_code == 404:
            return f"物料 {part_id} 无库存记录"
        resp.raise_for_status()
        return json.dumps(resp.json(), ensure_ascii=False)
