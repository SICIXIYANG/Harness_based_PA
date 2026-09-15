"""沙箱生命周期管理。

按用户作用域管理沙箱，实现三件核心能力：复用（缓存）、健康检查、故障重建（热替换）。
"""
from __future__ import annotations

from ..log_utils import get_logger
from .sandbox_proxy import SandboxProxy
from .sandbox_setup import connect_sandbox, create_sandbox, destroy_sandbox

logger = get_logger(__name__)


class SandboxManager:
    """管理 user_id -> SandboxProxy 的映射。"""

    def __init__(self) -> None:
        self._sandboxes: dict[str, SandboxProxy] = {}

    def get_sandbox(self, user_id: str) -> SandboxProxy:
        """获取用户的沙箱：健康则复用，故障则重建热替换，没有则新建。"""
        proxy = self._sandboxes.get(user_id)
        if proxy is not None:
            if self._is_healthy(proxy):
                return proxy
            return self.rebuild(user_id)
        return self._create(user_id)

    def rebuild(self, user_id: str) -> SandboxProxy:
        """沙箱故障时重建，并热替换到同一个 Proxy 上（上层无感知）。"""
        old = self._sandboxes.get(user_id)
        if old is not None:
            destroy_sandbox(old.backend)

        sandbox = create_sandbox(name=_sandbox_name(user_id))
        if old is not None:
            old.replace_backend(sandbox)
            logger.warning("为用户 %s 重建沙箱 %s", user_id, sandbox.id[:12])
            return old

        proxy = SandboxProxy(sandbox)
        self._sandboxes[user_id] = proxy
        return proxy

    def destroy(self, user_id: str) -> None:
        proxy = self._sandboxes.pop(user_id, None)
        if proxy is not None:
            destroy_sandbox(proxy.backend)

    def _create(self, user_id: str) -> SandboxProxy:
        name = _sandbox_name(user_id)
        # 有同名容器就先连接复用，没有才新建（跨进程也能复用）
        sandbox = connect_sandbox(name) or create_sandbox(name=name)
        proxy = SandboxProxy(sandbox)
        self._sandboxes[user_id] = proxy
        logger.info("为用户 %s 使用沙箱 %s", user_id, sandbox.id[:12])
        return proxy

    def _is_healthy(self, proxy: SandboxProxy) -> bool:
        """健康检查：ping 一下沙箱，能正常响应说明健康。"""
        try:
            result = proxy.execute("echo ok")
            return result.exit_code == 0
        except Exception:  # noqa: BLE001
            return False


def _sandbox_name(user_id: str) -> str:
    # 容器名不能含特殊字符，做一次简单清洗
    safe = "".join(ch if ch.isalnum() else "-" for ch in user_id)[:24]
    return f"procurement-{safe}"
