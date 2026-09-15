"""物料查询 MCP 工具：part_query / part_search / part_by_supplier。"""
from __future__ import annotations

import json

from mcp.server.mcpserver import MCPServer

from ..http_base import get_client


def register(server: MCPServer) -> None:
    @server.tool()
    async def part_query(part_id: str) -> str:
        """查询单个物料的详细信息（名称、分类、单位、单价、供应商）。

        Args:
            part_id: 物料编号，例如 P003
        """
        resp = await get_client().get(f"/api/parts/{part_id}")
        if resp.status_code == 404:
            return f"物料 {part_id} 不存在"
        resp.raise_for_status()
        return json.dumps(resp.json(), ensure_ascii=False)

    @server.tool()
    async def part_search(keyword: str) -> str:
        """按关键字搜索物料（匹配名称或分类）。

        Args:
            keyword: 关键字，例如 轴承 或 电子
        """
        resp = await get_client().get("/api/parts/search", params={"keyword": keyword})
        resp.raise_for_status()
        return json.dumps(resp.json(), ensure_ascii=False)

    @server.tool()
    async def part_by_supplier(supplier_id: str) -> str:
        """查询某个供应商提供的所有物料。

        Args:
            supplier_id: 供应商编号，例如 S001
        """
        resp = await get_client().get(f"/api/parts/by-supplier/{supplier_id}")
        resp.raise_for_status()
        return json.dumps(resp.json(), ensure_ascii=False)
