"""沙箱熔断器中间件（中间件矩阵 #7）。

监控沙箱健康检查的连续失败次数：连续失败达到阈值就「熔断打开」，
后续请求直接快速失败（不再尝试重建），冷却一段时间后才允许一次
探测请求（半开），探测成功则恢复关闭。

与 #1 SandboxHealthMiddleware 形成「两级防护」：
  #1 乐观恢复——每次请求 ping + 故障重建；
  #7 熔断兜底——持续故障时快速失败，避免反复重建拖垮服务。

熔断状态按 user_id 存模块级字典，跨请求（甚至跨中间件实例）保留，
因为熔断的本质就是「记住最近连续失败了几次」。

注意：本中间件必须在 SandboxHealthMiddleware 之前执行，才能拦下
「持续故障」——所以虽然编号是 #7，在 middleware 列表里要放最前面。
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from langchain.agents.middleware.types import AgentMiddleware

from ..backends.sandbox_manager import SandboxManager
from ..log_utils import get_logger

logger = get_logger(__name__)


@dataclass
class _BreakerState:
    failures: int = 0
    opened_at: float | None = None  # 熔断打开的时刻（monotonic 秒）

    def is_open(self, now: float, cooldown: float) -> bool:
        """熔断是否处于打开且冷却期内。"""
        return self.opened_at is not None and (now - self.opened_at) < cooldown

    def record_failure(self, now: float, threshold: int) -> bool:
        """记录一次失败，返回「本次是否打开了熔断」。"""
        if self.opened_at is not None:
            # 半开状态下的探测也失败 → 立即重新打开并重新计时
            self.opened_at = now
            self.failures = 0
            return True
        self.failures += 1
        if self.failures >= threshold:
            self.opened_at = now
            self.failures = 0
            return True
        return False

    def reset(self) -> None:
        self.failures = 0
        self.opened_at = None


# 进程内共享：按 user_id 记住熔断状态
_states: dict[str, _BreakerState] = {}


def _get_state(user_id: str) -> _BreakerState:
    return _states.setdefault(user_id, _BreakerState())


class SandboxCircuitBreakerMiddleware(AgentMiddleware):
    """持续故障时熔断，快速失败；冷却后自动探测恢复。"""

    def __init__(
        self,
        sandbox_manager: SandboxManager,
        user_id: str,
        failure_threshold: int = 3,
        cooldown_seconds: float = 60.0,
    ) -> None:
        self._sandbox_manager = sandbox_manager
        self._user_id = user_id
        self._threshold = failure_threshold
        self._cooldown = cooldown_seconds

    def _check(self) -> None:
        state = _get_state(self._user_id)
        now = time.monotonic()

        # 熔断打开且还在冷却期 → 快速失败，不碰沙箱
        if state.is_open(now, self._cooldown):
            raise RuntimeError(
                f"沙箱熔断器已打开（连续 {self._threshold} 次故障），"
                f"冷却 {self._cooldown:.0f}s 后自动恢复"
            )

        # 关闭 / 半开状态 → 尝试健康检查（get_sandbox 内部 ping + 故障重建）
        try:
            proxy = self._sandbox_manager.get_sandbox(self._user_id)
        except Exception as e:  # noqa: BLE001
            opened = state.record_failure(now, self._threshold)
            if opened:
                logger.error("[SandboxBreaker] 熔断打开：%s", e)
            else:
                logger.warning(
                    "[SandboxBreaker] 沙箱故障（%d/%d）：%s",
                    state.failures,
                    self._threshold,
                    e,
                )
            raise

        state.reset()
        logger.info("[SandboxBreaker] 沙箱健康，熔断器复位: %s", proxy.id[:12])

    def before_agent(self, state: Any, runtime: Any) -> dict[str, Any] | None:
        self._check()
        return None

    async def abefore_agent(self, state: Any, runtime: Any) -> dict[str, Any] | None:
        self._check()
        return None
