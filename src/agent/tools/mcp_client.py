"""MCP Client：把 MCP Server 暴露的工具动态转换成 LangChain 工具。

流程：
1. 通过 streamable-http 协议连接 MCP Server；
2. 拉取所有工具（name + description + input_schema）；
3. 用 pydantic.create_model 按 JSON Schema 动态生成入参模型；
4. 用 StructuredTool.from_function 把每个工具包成 LangChain 工具；
5. 调用时，每次新建一个 MCP 会话（无状态），调用完即关。

为什么每次新建会话？因为我们的 MCP 工具都是无状态的（只是把请求转发给
Mock ERP），不需要在多次调用之间共享状态；每次新建会话还能天然规避
「MCP Server 重启后旧会话失效」的问题。
"""
from __future__ import annotations

from typing import Any

from langchain_core.tools import BaseTool, StructuredTool
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from pydantic import create_model

from ..config import settings
from ..log_utils import get_logger

logger = get_logger(__name__)

# MCP Server 监听地址：0.0.0.0 只能作为服务端绑定地址，客户端要连 127.0.0.1
_host = settings.MCP_HOST
if _host in ("0.0.0.0", "::"):
    _host = "127.0.0.1"
MCP_URL = f"http://{_host}:{settings.MCP_PORT}/mcp"

# JSON Schema 类型 -> Python 类型
_JSON_TYPE_MAP: dict[str, type] = {
    "string": str,
    "integer": int,
    "number": float,
    "boolean": bool,
}


def _field_type(prop: dict[str, Any]) -> type:
    if "anyOf" in prop:
        for sub in prop["anyOf"]:
            t = sub.get("type")
            if t and t != "null":
                return _JSON_TYPE_MAP.get(t, str)
        return str
    return _JSON_TYPE_MAP.get(prop.get("type", "string"), str)


def _is_optional(prop: dict[str, Any], required: bool) -> bool:
    if not required:
        return True
    if "anyOf" in prop and any(s.get("type") == "null" for s in prop["anyOf"]):
        return True
    return False


def _schema_to_model(name: str, schema: dict[str, Any]) -> type:
    """按 JSON Schema 动态生成 Pydantic 入参模型。"""
    properties: dict[str, Any] = schema.get("properties", {}) or {}
    required: set[str] = set(schema.get("required", []) or [])
    fields: dict[str, Any] = {}
    for field_name, prop in properties.items():
        py_type = _field_type(prop)
        if _is_optional(prop, field_name in required):
            fields[field_name] = (py_type, None)
        else:
            fields[field_name] = (py_type, ...)
    return create_model(f"MCP_{name}_args", **fields)


async def _call_mcp_tool(name: str, arguments: dict[str, Any]) -> str:
    """开一个全新会话调用 MCP 工具，返回文本结果。"""
    async with streamable_http_client(MCP_URL) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(name, arguments)

    if result.is_error:
        return f"[工具调用失败] {name}"

    texts: list[str] = []
    for item in result.content:
        text = getattr(item, "text", None)
        if text is not None:
            texts.append(text)
    if texts:
        return "\n".join(texts)
    return "[]"


def _make_caller(name: str):
    """生成一个只接收工具参数、内部转发到 MCP 的协程。"""

    async def _call(**arguments: Any) -> str:
        return await _call_mcp_tool(name, arguments)

    return _call


async def load_mcp_tools() -> list[BaseTool]:
    """连接 MCP Server，把它的工具全部加载为 LangChain 工具。"""
    async with streamable_http_client(MCP_URL) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            listed = await session.list_tools()

    tools: list[BaseTool] = []
    for tool in listed.tools:
        model = _schema_to_model(tool.name, tool.input_schema or {})
        langchain_tool = StructuredTool.from_function(
            coroutine=_make_caller(tool.name),
            name=tool.name,
            description=tool.description or "",
            args_schema=model,
            infer_schema=False,
        )
        tools.append(langchain_tool)
        logger.info("已加载 MCP 工具: %s", tool.name)
    return tools
