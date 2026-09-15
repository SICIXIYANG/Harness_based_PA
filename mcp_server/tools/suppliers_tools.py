"""供应商查询 MCP 工具。"""
from __future__ import annotations

import json

from mcp.server.mcpserver import MCPServer

from ..http_base import get_client


def register(server: MCPServer) -> None:
    @server.tool()
    async def supplier_query(supplier_id: str) -> str:
        """查询单个供应商的详细信息（名称、分类、评级、联系人、联系方式）。

        Args:
            supplier_id: 供应商编号，例如 S001
        """
        resp = await get_client().get(f"/api/suppliers/{supplier_id}")
        if resp.status_code == 404:
            return f"供应商 {supplier_id} 不存在"
        resp.raise_for_status()
        return json.dumps(resp.json(), ensure_ascii=False)

    @server.tool()
    async def supplier_create(
        name: str,
        category: str | None = None,
        rating: float | None = None,
        contact: str | None = None,
        phone: str | None = None,
        email: str | None = None,
    ) -> str:
        """新增一个供应商（例如研究员在网上调研到的新供应商），返回生成的供应商编号。

        Args:
            name: 供应商名称，例如「XX 新钢厂」
            category: 品类（可选），例如 钢材
            rating: 评级（可选），例如 4.5
            contact: 联系人（可选）
            phone: 电话（可选）
            email: 邮箱（可选）
        """
        payload: dict = {"name": name}
        if category is not None:
            payload["category"] = category
        if rating is not None:
            payload["rating"] = rating
        if contact is not None:
            payload["contact"] = contact
        if phone is not None:
            payload["phone"] = phone
        if email is not None:
            payload["email"] = email
        resp = await get_client().post("/api/suppliers", json=payload)
        resp.raise_for_status()
        return json.dumps(resp.json(), ensure_ascii=False)
