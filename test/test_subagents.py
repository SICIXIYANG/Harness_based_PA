"""验证 Subagent 能力：主 Agent 通过 task 工具把活派给专职子 Agent，再汇总结论。

运行前：启动 Mock ERP + MCP Server（MongoDB + 沙箱 Docker 需在跑）。
运行：python test/test_subagents.py
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
        "请把下面两个采购任务分别派给对应的子智能体，最后汇总：\n"
        "1) 采购执行员(procurement-executor)：查当前库存预警，并查物料 P003 的详情；\n"
        "2) 采购研究员(procurement-researcher)：在网上调研 6204 深沟球轴承"
        "(deep groove ball bearing)的行情，给出买哪个好的建议。"
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
                print(f"   [工具] {tc.get('name')}({tc.get('args')})")

    final = chunk.get("messages", [])[-1]
    print("\n=== 最终回答 ===")
    print(getattr(final, "content", ""))

    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
