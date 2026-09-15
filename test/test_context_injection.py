"""验证 ContextInjectionMiddleware：把用户偏好记忆注入 system prompt。

运行前：MongoDB + 沙箱 Docker 需在跑（不需要 LLM / MCP）。
运行：python test/test_context_injection.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.agent.backends.backend_factory import build_backend
from src.agent.backends.sandbox_proxy import SandboxProxy
from src.agent.backends.sandbox_setup import create_sandbox, destroy_sandbox
from src.agent.middlewares.context_injection import ContextInjectionMiddleware


class _FakeRequest:
    """极简 ModelRequest 替身：只实现 override + system_message 两个用到的点。"""

    def __init__(self, system_message=None) -> None:
        self.system_message = system_message

    def override(self, **kwargs):
        return _FakeRequest(kwargs.get("system_message", self.system_message))


def main() -> None:
    sandbox = create_sandbox()
    proxy = SandboxProxy(sandbox)
    backend = build_backend(proxy)

    # 0. 清理 + 写入一条偏好
    backend.delete("/memories/default_user/preferences.md")
    backend.write(
        "/memories/default_user/preferences.md",
        "# 用户偏好记忆\n\npreferred_chart_type: pie\npreferred_currency: USD\n",
    )

    mw = ContextInjectionMiddleware(backend, "default_user")

    # 1. 有偏好 → 注入到 system message
    captured: dict = {}

    def handler(req):
        captured["blocks"] = req.system_message.content_blocks
        return "resp"

    mw.wrap_model_call(_FakeRequest(None), handler)
    text = captured["blocks"][-1]["text"]
    print("   注入到 system message 的内容：")
    print("   " + text.replace("\n", "\n   ") + "\n")
    assert "preferred_chart_type: pie" in text, text
    assert "preferred_currency: USD" in text, text
    assert "<user_preferences>" in text, text
    print("   有偏好时注入成功 ✓")

    # 2. 无偏好文件 → 不注入（system_message 保持 None）
    backend.delete("/memories/default_user/preferences.md")
    captured2: dict = {}

    def handler2(req):
        captured2["blocks"] = req.system_message.content_blocks if req.system_message else None
        return "resp"

    mw.wrap_model_call(_FakeRequest(None), handler2)
    assert captured2["blocks"] is None, "无偏好时不应注入 system message"
    print("   无偏好时不注入 ✓")

    destroy_sandbox(sandbox)
    print("\nDone.")


if __name__ == "__main__":
    main()
