"""验证 UserSkillsRestoreMiddleware：沙箱重建后，从 MongoDB 恢复用户技能。

运行前：MongoDB + 沙箱 Docker 需在跑（不需要 LLM / MCP）。
运行：python test/test_user_skills_restore.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.agent.backends.backend_factory import build_backend
from src.agent.backends.sandbox_manager import SandboxManager
from src.agent.middlewares.user_skills_restore import UserSkillsRestoreMiddleware


def main() -> None:
    sm = SandboxManager()
    sandbox = sm.get_sandbox("default_user")
    backend = build_backend(sandbox)

    # 0. 清理旧数据，保证测试可重复
    backend.delete("/persisted-skills/")

    # 1. 模拟「运行时已把用户技能持久化到 MongoDB」
    backend.write("/persisted-skills/user-tip.md", "# 用户自定义技能\n只报告异常供应商\n")

    # 2. 模拟故障重建（热替换到同一个 proxy）
    sm.rebuild("default_user")

    # 3. 触发恢复
    mw = UserSkillsRestoreMiddleware(sm, "default_user", backend)
    n = mw._restore()
    print(f"恢复文件数：{n}（应为 1）")

    # 4. 验证沙箱里有恢复的文件
    proxy = sm.get_sandbox("default_user")
    resp = proxy.download_files(["/skills/user/user-tip.md"])[0]
    if resp.error or resp.content is None:
        print("恢复失败：沙箱里没找到 /skills/user/user-tip.md")
    else:
        print(f"沙箱 /skills/user/user-tip.md 内容：{resp.content.decode('utf-8')!r}")

    print("\nDone.")


if __name__ == "__main__":
    main()
