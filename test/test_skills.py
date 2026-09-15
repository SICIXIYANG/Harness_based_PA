"""验证 Skills 能力：Agent 能渐进式发现技能，并在需要时读取技能手册。

运行前：启动 Mock ERP + MCP Server（MongoDB + 沙箱 Docker 需在跑）。
运行：python test/test_skills.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Windows 控制台默认 GBK，遇到 ¥ 等符号会崩，统一切成 UTF-8 输出
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.agent.main_agent import create_main_agent


async def main() -> None:
    agent = await create_main_agent()

    question = "查一下当前有哪些库存预警，并给出补货建议。"
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
