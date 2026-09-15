"""持久化技能恢复中间件（中间件矩阵 #4）。

沙箱重建后，把 MongoDB /persisted-skills/ 里持久化的「用户运行时进化出的
技能」恢复到沙箱 /skills/user/，与本地技能 /skills/procurement/ 分开存放。
"""
from __future__ import annotations

from typing import Any

from langchain.agents.middleware.types import AgentMiddleware

from ..backends.sandbox_manager import SandboxManager
from ..log_utils import get_logger

logger = get_logger(__name__)

PERSISTED_SKILLS_PATH = "/persisted-skills"
SANDBOX_USER_SKILLS_PATH = "/skills/user"


def _list_files_recursive(backend, path: str) -> list[str]:
    """递归列出 backend 上 path 目录下的所有文件路径。"""
    result: list[str] = []
    ls = backend.ls(path)
    for entry in (ls.entries or []):
        if entry.get("is_dir"):
            result.extend(_list_files_recursive(backend, entry["path"]))
        else:
            result.append(entry["path"])
    return result


class UserSkillsRestoreMiddleware(AgentMiddleware):
    """每次 Agent 运行前，把持久化在 MongoDB 的用户技能恢复到沙箱。"""

    def __init__(self, sandbox_manager: SandboxManager, user_id: str, backend) -> None:
        self._sandbox_manager = sandbox_manager
        self._user_id = user_id
        self._backend = backend

    def _restore(self) -> int:
        proxy = self._sandbox_manager.get_sandbox(self._user_id)

        paths = _list_files_recursive(self._backend, PERSISTED_SKILLS_PATH + "/")
        if not paths:
            return 0

        responses = self._backend.download_files(paths)
        files: list[tuple[str, bytes]] = []
        for resp in responses:
            if resp.error or resp.content is None:
                continue
            rel = resp.path.removeprefix(PERSISTED_SKILLS_PATH + "/")
            files.append((f"{SANDBOX_USER_SKILLS_PATH}/{rel}", resp.content))

        if files:
            proxy.upload_files(files)
            logger.info("[UserSkillsRestore] 已恢复 %d 个用户技能到沙箱", len(files))
        return len(files)

    def before_agent(self, state: Any, runtime: Any) -> dict[str, Any] | None:
        self._restore()
        return None

    async def abefore_agent(self, state: Any, runtime: Any) -> dict[str, Any] | None:
        self._restore()
        return None
