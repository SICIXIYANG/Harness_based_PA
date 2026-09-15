"""AgentLoader 单例：创建并持有主 Agent + checkpointer。

checkpointer 用 MemorySaver（内存版）：支撑 HITL 中断的「存档与恢复」。
每个 thread_id 对应一条独立对话线程，config 里用 thread_id 区分。
"""
from __future__ import annotations

from langgraph.checkpoint.memory import MemorySaver

from ..agent.main_agent import create_main_agent


class AgentLoader:
    def __init__(self) -> None:
        self._checkpointer = MemorySaver()
        self._agent = None

    async def get_agent(self):
        """懒加载：首次请求时才真正创建 Agent（加载 MCP 工具 + 中间件）。"""
        if self._agent is None:
            self._agent = await create_main_agent(checkpointer=self._checkpointer)
        return self._agent

    @staticmethod
    def create_config(thread_id: str) -> dict:
        return {"configurable": {"thread_id": thread_id}}


agent_loader = AgentLoader()
