"""验证 MCP Server：工具注册 + 直连 Mock ERP 调用。

运行前：先启动 Mock ERP（python -m mock_erp.main）。
运行：python test/test_mcp.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mcp_server.server_main import create_server


def _text(result) -> str:
    # 工具返回的是 JSON 字符串，放在 content[0].text 里
    if result.content:
        return result.content[0].text
    return f"(无内容, is_error={result.is_error})"


async def main() -> None:
    server = create_server()

    print("1. 列出所有 MCP 工具 ...")
    tools = await server.list_tools()
    for t in tools:
        print(f"   - {t.name}")

    print("2. 调用 supplier_query(S001) ...")
    r = await server.call_tool("supplier_query", {"supplier_id": "S001"})
    print(f"   {_text(r)}")

    print("3. 调用 part_search(轴承) ...")
    r = await server.call_tool("part_search", {"keyword": "轴承"})
    print(f"   {_text(r)}")

    print("4. 调用 inventory_warning() ...")
    r = await server.call_tool("inventory_warning", {})
    print(f"   {_text(r)}")

    print("5. 调用 order_create(P003, 5) ...")
    r = await server.call_tool("order_create", {"part_id": "P003", "quantity": 5})
    print(f"   {_text(r)}")

    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
