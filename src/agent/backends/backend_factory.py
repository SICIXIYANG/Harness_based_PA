"""三层路由文件系统：把 Agent 的“文件系统”按路径前缀路由到不同存储。

三层：
1. 默认层（default）＝沙箱文件系统（SandboxProxy）—— 临时工作文件、代码执行产物，随容器销毁。
2. /memories/          —— MongoDB 持久记忆，跨会话、跨重启保留。
3. /persisted-skills/  —— MongoDB 持久化技能，跨会话、跨重启保留。

Agent 读写 /memories/xx 时自动落到 MongoDB，读写 /workspace/xx 时自动落到沙箱，
上层（Agent / 工具）无需关心底层到底存在哪。
"""
from __future__ import annotations

from deepagents.backends.composite import CompositeBackend
from deepagents.backends.store import StoreBackend

from ..config import settings
from .mongo_store import MongoStore
from .sandbox_proxy import SandboxProxy


def build_backend(sandbox: SandboxProxy) -> CompositeBackend:
    """用给定的沙箱代理构建三层路由文件系统。"""
    store = MongoStore(settings.MONGO_URI, settings.MONGO_DB)

    return CompositeBackend(
        default=sandbox,
        routes={
            "/memories/": StoreBackend(namespace=lambda _rt: ("memories",), store=store),
            "/persisted-skills/": StoreBackend(namespace=lambda _rt: ("skills",), store=store),
        },
    )
