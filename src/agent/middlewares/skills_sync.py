"""技能增量同步中间件（中间件矩阵 #3）。

增量原理：本地给每个技能文件算内容哈希，和沙箱 /skills/manifest.json 里
记录的「上次同步哈希」做对比，只上传新增 / 变更的文件；首次（沙箱里没有
manifest）自动退化为全量上传。
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from langchain.agents.middleware.types import AgentMiddleware

from ..backends.sandbox_manager import SandboxManager
from ..backends.sandbox_proxy import SandboxProxy
from ..env_utils import project_root
from ..log_utils import get_logger

logger = get_logger(__name__)

SKILLS_DIR: Path = project_root() / "skills"
SANDBOX_SKILLS_PATH = "/skills"
MANIFEST_PATH = "/skills/manifest.json"


def _hash_bytes(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()


def _list_local_skills() -> dict[str, str]:
    """本地技能文件清单：{相对路径: 内容哈希}。"""
    result: dict[str, str] = {}
    if not SKILLS_DIR.exists():
        return result
    for path in SKILLS_DIR.rglob("*"):
        if path.is_file():
            rel = path.relative_to(SKILLS_DIR).as_posix()
            result[rel] = _hash_bytes(path.read_bytes())
    return result


def _read_manifest(sandbox: SandboxProxy) -> dict[str, str]:
    """读沙箱里上次同步的清单；不存在或损坏则返回空。"""
    try:
        responses = sandbox.download_files([MANIFEST_PATH])
        resp = responses[0]
        if resp.error or resp.content is None:
            return {}
        return json.loads(resp.content.decode("utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def sync_skills_incremental(sandbox: SandboxProxy) -> int:
    """增量同步本地技能到沙箱，返回本次上传的文件数。

    只上传「新增」或「内容变化」的文件，跳过未变的；同步完更新 manifest。
    首次调用（沙箱里没有 manifest）会退化为全量上传。
    """
    local = _list_local_skills()
    remote = _read_manifest(sandbox)

    changed = [rel for rel, h in local.items() if remote.get(rel) != h]
    if changed:
        files = [
            (f"{SANDBOX_SKILLS_PATH}/{rel}", (SKILLS_DIR / rel).read_bytes())
            for rel in changed
        ]
        sandbox.upload_files(files)
        logger.info("[SkillsSync] 已增量同步 %d 个技能文件", len(changed))

    # 清单和本地不一致时才回写（首次、或刚发生过变更）
    if local != remote:
        sandbox.upload_files(
            [(MANIFEST_PATH, json.dumps(local, ensure_ascii=False).encode("utf-8"))]
        )
    return len(changed)


class SkillsSyncMiddleware(AgentMiddleware):
    """每次 Agent 运行前把本地技能增量同步到沙箱。"""

    def __init__(self, sandbox_manager: SandboxManager, user_id: str) -> None:
        self._sandbox_manager = sandbox_manager
        self._user_id = user_id

    def _sync(self) -> None:
        # get_sandbox 保证沙箱活着（前面的 SandboxHealth 已经处理过重建），
        # 这里只管同步技能，不重复做健康检查。
        proxy = self._sandbox_manager.get_sandbox(self._user_id)
        sync_skills_incremental(proxy)

    def before_agent(self, state: Any, runtime: Any) -> dict[str, Any] | None:
        self._sync()
        return None

    async def abefore_agent(self, state: Any, runtime: Any) -> dict[str, Any] | None:
        self._sync()
        return None
