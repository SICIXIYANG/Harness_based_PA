"""用户上下文注入中间件（中间件矩阵 #2）。

每次模型调用前（wrap_model_call），把 /memories/{user_id}/preferences.md
读出来，注入到 system prompt，让 Agent 一开口就知道用户的长期偏好。

与 #6 MemoryUpdateMiddleware 配对：#6 在对话结束后「写」偏好，
本中间件在对话开始前「读」偏好注入，形成记忆闭环。
"""
from __future__ import annotations

from typing import Any

from deepagents.middleware._utils import append_to_system_message
from langchain.agents.middleware.types import AgentMiddleware

from ..log_utils import get_logger
from .memory_update import PREFERENCES_PATH

logger = get_logger(__name__)

_INJECT_TEMPLATE = (
    "<user_preferences>\n{preferences}\n</user_preferences>\n\n"
    "以上是用户的长期偏好记忆，请在回答时参考这些偏好"
    "（例如图表类型、输出风格、常用货币、最近关心的供应商等）。"
)


class ContextInjectionMiddleware(AgentMiddleware):
    """每次模型调用前，把用户偏好记忆注入 system prompt。"""

    def __init__(self, backend, user_id: str) -> None:
        self._backend = backend
        self._user_id = user_id

    def _path(self) -> str:
        return PREFERENCES_PATH.format(user_id=self._user_id)

    def _load(self) -> str:
        resp = self._backend.download_files([self._path()])[0]
        if resp.error or resp.content is None:
            return ""
        return resp.content.decode("utf-8").strip()

    def _inject(self, request: Any) -> Any:
        preferences = self._load()
        if not preferences:
            return request
        text = _INJECT_TEMPLATE.format(preferences=preferences)
        new_system = append_to_system_message(request.system_message, text)
        return request.override(system_message=new_system)

    def wrap_model_call(self, request: Any, handler: Any) -> Any:
        return handler(self._inject(request))

    async def awrap_model_call(self, request: Any, handler: Any) -> Any:
        return await handler(self._inject(request))
