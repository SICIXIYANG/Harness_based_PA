"""验证双流模式。

运行：在项目根目录激活虚拟环境后执行
    python test/test_stream.py

预期输出：
    - [messages] 流：逐 token 吐出（AIMessageChunk）
    - [values]  流：每一步的完整状态快照（state dict）
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.agent.config import settings
from src.agent.main_agent import create_main_agent


async def main() -> None:
    print(f"LLM model    : {settings.LLM_MODEL}")
    print(f"LLM base_url : {settings.LLM_BASE_URL}")
    print(f"API key set  : {'yes' if settings.LLM_API_KEY else 'NO - check env'}")
    print("=" * 60)

    agent = await create_main_agent()

    print("Start streaming (stream_mode=['messages', 'values']) ...\n")
    async for mode, chunk in agent.astream(
        {"messages": [{"role": "user", "content": "请分三步介绍你的职能"}]},
        stream_mode=["messages", "values"],
    ):
        if mode == "messages":
            msg, meta = chunk
            content = getattr(msg, "content", "") or ""
            if content:
                print(f"  [messages] token: {content!r}")
            else:
                print(f"  [messages] event: type={msg.type} meta={meta}")
        elif mode == "values":
            msgs = chunk.get("messages", [])
            print(f"  [values] state snapshot -> {len(msgs)} messages in state")

    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
