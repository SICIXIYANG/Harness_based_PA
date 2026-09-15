"""验证 Agent 能通过 MCP 加载工具，并用自然语言驱动工具调用。

运行前：
1. 启动 Mock ERP：python -m mock_erp.main
2. 启动 MCP Server：python -m mcp_server.server_main
3. 运行本测试：python test/test_agent_tools.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.agent.config import settings
from src.agent.main_agent import create_main_agent
from src.agent.tools.mcp_client import load_mcp_tools


async def main() -> None:
    print("1. 通过 MCP 加载工具 ...")
    tools = await load_mcp_tools()
    for t in tools:
        print(f"   - {t.name}: {t.description}")

    print("\n2. 创建主 Agent ...")
    agent = await create_main_agent()

    question = "帮我查一下物料 P003 的详细信息，包括它的供应商是谁"
    print(f"\n3. 提问：{question}\n")

    async for chunk in agent.astream(
        {"messages": [{"role": "user", "content": question}]},
        stream_mode="values",
    ):
        msgs = chunk.get("messages", [])
        if not msgs:
            continue
        last = msgs[-1]
        # 只打印 AI 的最终文本和它发起的工具调用，跳过中间 token 刷屏
        if getattr(last, "type", "") == "ai":
            for tc in getattr(last, "tool_calls", []) or []:
                print(f"   [工具调用] {tc.get('name')}({tc.get('args')})")
        elif getattr(last, "type", "") == "tool":
            print(f"   [工具结果] {str(last.content)[:120]}")

    final = chunk.get("messages", [])[-1]
    print("\n=== 最终回答 ===")
    print(getattr(final, "content", ""))

    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
