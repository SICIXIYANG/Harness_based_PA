"""验证 SandboxCircuitBreakerMiddleware：状态机 + 熔断快速失败 + 恢复。

纯逻辑测试，用假 SandboxManager，不需要沙箱 Docker / MongoDB / LLM。
运行：python test/test_sandbox_breaker.py
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.agent.middlewares import sandbox_breaker as sb


class _FakeManager:
    """假 SandboxManager：可切换 get_sandbox 成功/失败，并记录调用次数。"""

    def __init__(self, fail: bool = True) -> None:
        self.fail = fail
        self.calls = 0

    def get_sandbox(self, user_id: str):
        self.calls += 1
        if self.fail:
            raise RuntimeError("沙箱不可达")
        return SimpleNamespace(id="fake-sandbox-id")


def test_state_machine() -> None:
    print("【A. 状态机单测】")
    s = sb._BreakerState()
    assert not s.is_open(0.0, 60)

    # 连续失败 3 次才打开
    assert not s.record_failure(0.0, 3)  # 1/3
    assert not s.record_failure(0.0, 3)  # 2/3
    assert s.record_failure(0.0, 3)  # 3/3 → 打开
    assert s.is_open(0.0, 60)  # 冷却期内打开
    assert not s.is_open(61.0, 60)  # 冷却结束 → 半开

    # 半开探测失败 → 立即重新打开并重新计时
    assert s.record_failure(61.0, 3)
    assert s.is_open(61.0, 60)

    s.reset()
    assert not s.is_open(0.0, 60)
    print("   状态机测试通过 ✓\n")


def test_breaker_opens() -> None:
    print("【B. 连续失败 → 熔断打开 → 快速失败】")
    sb._states.clear()
    mgr = _FakeManager(fail=True)
    mw = sb.SandboxCircuitBreakerMiddleware(mgr, "u", failure_threshold=3, cooldown_seconds=60)

    # 前 3 次失败：每次都会尝试 get_sandbox
    for _ in range(3):
        try:
            mw.before_agent(None, None)
        except RuntimeError:
            pass
    assert mgr.calls == 3, mgr.calls

    # 第 4 次：熔断已打开，应快速失败且不再调 get_sandbox
    calls_before = mgr.calls
    try:
        mw.before_agent(None, None)
    except RuntimeError as e:
        assert "熔断" in str(e), str(e)
    assert mgr.calls == calls_before, "熔断打开后不应再调 get_sandbox"
    print("   熔断快速失败测试通过 ✓\n")


def test_recovery() -> None:
    print("【C. 沙箱恢复后 → 熔断器复位】")
    sb._states.clear()
    mgr = _FakeManager(fail=False)
    mw = sb.SandboxCircuitBreakerMiddleware(mgr, "u2", failure_threshold=3, cooldown_seconds=60)

    # 健康沙箱：直接通过，不抛异常
    mw.before_agent(None, None)
    assert mgr.calls == 1
    assert sb._states["u2"].failures == 0
    assert sb._states["u2"].opened_at is None
    print("   恢复测试通过 ✓\n")


if __name__ == "__main__":
    test_state_machine()
    test_breaker_opens()
    test_recovery()
    print("Done.")
