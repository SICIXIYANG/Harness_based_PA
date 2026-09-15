"""验证 HITL 能力：双层中断（第 1 层数据补充 + 第 2 层最终审批）。

运行前：启动 Mock ERP + MCP Server（MongoDB + 沙箱 Docker 需在跑）。
运行：python test/test_hitl.py
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Windows 控制台默认 GBK，遇到 ¥ 等符号会崩，统一切成 UTF-8 输出
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from src.agent.main_agent import create_main_agent


async def stream_until_interrupt(agent, input_, config):
    """流式运行，遇到中断就返回中断的 value；没遇到返回 None。"""
    async for chunk in agent.astream(input_, config=config, stream_mode="updates"):
        if "__interrupt__" in chunk:
            return chunk["__interrupt__"][0].value
    return None


async def main() -> None:
    agent = await create_main_agent(checkpointer=MemorySaver())
    config = {"configurable": {"thread_id": "hitl-demo"}}

    question = (
        "帮我创建一个采购订单。现在缺物料编号和数量，"
        "请调用 request_order_info 工具向我询问缺失信息。"
    )
    print(f"提问：{question}\n")

    # 第 1 层：数据补充（缺物料编号 / 数量）
    layer1 = await stream_until_interrupt(
        agent, {"messages": [{"role": "user", "content": question}]}, config
    )
    print("=== 第 1 层中断（数据补充）===")
    print(json.dumps(layer1, ensure_ascii=False, indent=2))

    # 恢复：补充物料和数量 → 触发第 2 层审批
    layer2 = await stream_until_interrupt(
        agent, Command(resume={"supplement": "物料编号 P002，数量 100"}), config
    )
    print("\n=== 第 2 层中断（最终审批）===")
    print(json.dumps(layer2, ensure_ascii=False, indent=2))

    # 恢复：批准 → 订单真正创建
    print("\n=== 批准后继续执行 ===")
    final = None
    async for chunk in agent.astream(
        Command(resume={"decisions": [{"type": "approve"}]}),
        config=config,
        stream_mode="values",
    ):
        final = chunk

    msgs = final.get("messages", []) if final else []
    if msgs:
        print(getattr(msgs[-1], "content", ""))

    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
