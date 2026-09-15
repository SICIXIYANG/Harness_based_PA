"""验证 Memory 能力：用户偏好跨会话持久化（存在 MongoDB 里）。

运行前：启动 Mock ERP + MCP Server（MongoDB 容器 + 沙箱容器需在跑）。
运行：python test/test_memory.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pymongo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.agent.config import settings
from src.agent.main_agent import create_main_agent


def _show_mongodb() -> None:
    client = pymongo.MongoClient(settings.MONGO_URI)
    coll = client[settings.MONGO_DB]["langgraph_store"]
    docs = list(coll.find({"namespace": ["memories"]}))
    print("   MongoDB 里现在存了这些记忆：")
    for d in docs:
        print(f"     - 文件名={d['key']}, 内容={d['value']}")
    if not docs:
        print("     （空）")


async def main() -> None:
    # ===== 会话 1：让 Agent 记住偏好 =====
    print("【会话 1】让 Agent 记住一个偏好 ...\n")
    agent1 = await create_main_agent()
    r1 = await agent1.ainvoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": "请记住：我以后做采购分析时，图表都用饼图。"
                    "把这条偏好保存到 /memories/preferences.md 文件里。",
                }
            ]
        }
    )
    print(f"   Agent 回答：{getattr(r1['messages'][-1], 'content', '')[:200]}\n")

    print("   检查 MongoDB：")
    _show_mongodb()
    print()

    # ===== 会话 2：全新 Agent，验证还记得 =====
    print("【会话 2】开一个全新的 Agent，问它偏好 ...\n")
    agent2 = await create_main_agent()
    r2 = await agent2.ainvoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": "先读取 /memories/preferences.md 文件，"
                    "然后告诉我：做采购分析时我喜欢的图表类型是什么？",
                }
            ]
        }
    )
    print(f"   Agent 回答：{getattr(r2['messages'][-1], 'content', '')}\n")

    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
