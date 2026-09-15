"""验证 SandboxHealthMiddleware：每次运行前检查沙箱健康，故障自动重建。

运行前：启动 Mock ERP + MCP Server（MongoDB 需在跑）。
运行：python test/test_sandbox_health.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import docker

from src.agent.main_agent import create_main_agent


async def ask(agent, question: str) -> str:
    final = None
    async for chunk in agent.astream(
        {"messages": [{"role": "user", "content": question}]},
        stream_mode="values",
    ):
        final = chunk
    return getattr(final["messages"][-1], "content", "")


async def main() -> None:
    agent = await create_main_agent()

    print("=== 第一次提问（沙箱健康）===")
    ans1 = await ask(agent, "帮我查一下物料 P001 的详情。")
    print(ans1)

    # 人为干掉沙箱容器
    client = docker.from_env()
    container = client.containers.get("procurement-default-user")
    container.remove(force=True)
    print("\n>>> 已人为销毁沙箱容器 procurement-default-user\n")

    print("=== 第二次提问（应触发自动重建）===")
    ans2 = await ask(agent, "再帮我查一下物料 P002 的详情。")
    print(ans2)

    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
