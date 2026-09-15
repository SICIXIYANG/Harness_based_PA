"""采购订单 MCP 工具：order_create / order_update / order_search_details。"""
from __future__ import annotations

import json

from mcp.server.mcpserver import MCPServer

from ..http_base import get_client


def register(server: MCPServer) -> None:
    @server.tool()
    async def order_create(
        part_id: str,
        quantity: int,
        unit_price: float | None = None,
        order_type: str = "purchase",
        supplier_id: str | None = None,
    ) -> str:
        """新建订单。

        Args:
            part_id: 物料编号，例如 P003
            quantity: 数量
            unit_price: 单价，不传则用物料默认价
            order_type: 订单类型，purchase=采购入库(库存+)，sale=销售出库(库存-)
            supplier_id: 供应商编号（可选），不传则用物料的默认供应商；
                若下单给 ERP 里还没有的新供应商，请先调用 supplier_create 注册拿到编号
        """
        payload: dict = {
            "part_id": part_id,
            "quantity": quantity,
            "order_type": order_type,
        }
        if unit_price is not None:
            payload["unit_price"] = unit_price
        if supplier_id is not None:
            payload["supplier_id"] = supplier_id
        resp = await get_client().post("/api/orders", json=payload)
        if resp.status_code == 404:
            return f"[未找到] {resp.json().get('detail', '')}"
        resp.raise_for_status()
        return json.dumps(resp.json(), ensure_ascii=False)

    @server.tool()
    async def order_update(
        order_id: str,
        quantity: int | None = None,
        unit_price: float | None = None,
        status: str | None = None,
    ) -> str:
        """修改采购订单，只更新传入的字段。

        Args:
            order_id: 订单编号，例如 O0001
            quantity: 新采购数量
            unit_price: 新单价
            status: 新状态（pending/approved/placed/received/cancelled）
        """
        payload: dict = {}
        if quantity is not None:
            payload["quantity"] = quantity
        if unit_price is not None:
            payload["unit_price"] = unit_price
        if status is not None:
            payload["status"] = status
        resp = await get_client().put(f"/api/orders/{order_id}", json=payload)
        if resp.status_code == 404:
            return f"订单 {order_id} 不存在"
        resp.raise_for_status()
        return json.dumps(resp.json(), ensure_ascii=False)

    @server.tool()
    async def order_search_details(order_id: str) -> str:
        """查询某个采购订单的详情。

        Args:
            order_id: 订单编号，例如 O0001
        """
        resp = await get_client().get(f"/api/orders/{order_id}")
        if resp.status_code == 404:
            return f"订单 {order_id} 不存在"
        resp.raise_for_status()
        return json.dumps(resp.json(), ensure_ascii=False)

    @server.tool()
    async def order_list() -> str:
        """列出所有采购订单。"""
        resp = await get_client().get("/api/orders")
        resp.raise_for_status()
        return json.dumps(resp.json(), ensure_ascii=False)

    @server.tool()
    async def order_place(order_id: str) -> str:
        """执行下单：采购订单入库（库存+），销售订单出库（库存-）。

        Args:
            order_id: 订单编号，例如 O0001
        """
        resp = await get_client().post(f"/api/orders/{order_id}/place")
        if resp.status_code == 404:
            return f"订单 {order_id} 不存在"
        if resp.status_code == 400:
            return f"[库存不足] {resp.json().get('detail', '')}"
        resp.raise_for_status()
        return json.dumps(resp.json(), ensure_ascii=False)
