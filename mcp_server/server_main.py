"""MCP Server 入口：把 Mock ERP 的 HTTP 接口包装成 MCP 工具。

运行：python -m mcp_server.server_main
"""
from __future__ import annotations

from mcp.server.mcpserver import MCPServer

from . import server_config
from .tools import inventory_tools, order_tools, parts_tools, suppliers_tools


def create_server() -> MCPServer:
    server = MCPServer(name="procurement-mcp", version="0.1.0")
    suppliers_tools.register(server)
    parts_tools.register(server)
    order_tools.register(server)
    inventory_tools.register(server)
    return server


if __name__ == "__main__":
    server = create_server()
    server.run(
        transport="streamable-http",
        host=server_config.MCP_HOST,
        port=server_config.MCP_PORT,
    )
