"""沙箱健康中间件（中间件矩阵 #1）。

在 before_agent 钩子里做沙箱健康检查：健康则复用，故障则交给
SandboxManager 自动重建并热替换（上层无感知）。
"""
from __future__ import annotations

from typing import Any

from langchain.agents.middleware.types import AgentMiddleware

from ..backends.sandbox_manager import SandboxManager
from ..log_utils import get_logger

logger = get_logger(__name__)


class SandboxHealthMiddleware(AgentMiddleware):
    """每次 Agent 运行前检查沙箱健康，故障自动重建。"""

    def __init__(self, sandbox_manager: SandboxManager, user_id: str) -> None:
        self._sandbox_manager = sandbox_manager
        self._user_id = user_id

    def _check(self) -> None:
        # get_sandbox 内部：健康则复用，故障则 rebuild 热替换，没有则新建。
        # 技能同步交给紧随其后的 SkillsSyncMiddleware，这里只负责「活着」。
        proxy = self._sandbox_manager.get_sandbox(self._user_id)
        logger.info("[SandboxHealth] 沙箱健康检查通过: %s", proxy.id[:12])

    def before_agent(self, state: Any, runtime: Any) -> dict[str, Any] | None:
        self._check()
        return None

    async def abefore_agent(self, state: Any, runtime: Any) -> dict[str, Any] | None:
        self._check()
        return None
