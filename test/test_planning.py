"""验证 Planning 能力：Agent 遇到多步任务时，会先调用 write_todos 列计划。

运行前：
1. 启动 Mock ERP：python -m mock_erp.main
2. 启动 MCP Server：python -m mcp_server.server_main
3. 运行本测试：python test/test_planning.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.agent.main_agent import create_main_agent


async def main() -> None:
    agent = await create_main_agent()

    question = (
        "这是一个多步骤任务，请先用 write_todos 工具列出计划，再逐步执行："
        "1) 查询当前所有库存预警的物料；"
        "2) 对每个预警物料，查出它的供应商和联系人；"
        "3) 最后汇总给出采购建议。"
        "全程请用中文回答。"
    )
    print(f"提问：{question}\n")

    async for chunk in agent.astream(
        {"messages": [{"role": "user", "content": question}]},
        stream_mode="values",
    ):
        msgs = chunk.get("messages", [])
        if not msgs:
            continue
        last = msgs[-1]
        if getattr(last, "type", "") == "ai":
            for tc in getattr(last, "tool_calls", []) or []:
                name = tc.get("name")
                if name == "write_todos":
                    todos = tc.get("args", {}).get("todos", [])
                    print("\n【计划】Agent 用 write_todos 列出了任务清单：")
                    for t in todos:
                        print(f"   - [{t['status']}] {t['content']}")
                else:
                    print(f"   [工具] {name}({tc.get('args')})")

    final = chunk.get("messages", [])[-1]
    print("\n=== 最终回答 ===")
    print(getattr(final, "content", ""))

    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
