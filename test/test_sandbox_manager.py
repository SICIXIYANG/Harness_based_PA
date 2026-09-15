"""验证沙箱生命周期管理：复用 + 故障重建（热替换）。

运行：python test/test_sandbox_manager.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.agent.backends.sandbox_manager import SandboxManager


def main() -> None:
    manager = SandboxManager()

    print("1. 第一次获取 user1 的沙箱（新建）...")
    proxy1 = manager.get_sandbox("user1")
    print(f"   proxy1 沙箱 id = {proxy1.id[:12]}")

    print("2. 再次获取 user1 的沙箱（应复用同一个）...")
    proxy2 = manager.get_sandbox("user1")
    print(f"   proxy2 沙箱 id = {proxy2.id[:12]}")
    print(f"   是同一个 proxy 对象吗？ {proxy1 is proxy2}")

    print("3. 在沙箱里写一个文件 ...")
    w = proxy1.write("/workspace/note.txt", "remember me\n")
    print(f"   write error = {w.error}")

    print("4. 模拟故障：直接删掉底层容器 ...")
    proxy1.backend.container.remove(force=True)
    print("   底层容器已删除")

    print("5. 再次获取（健康检查会失败，触发重建热替换）...")
    proxy3 = manager.get_sandbox("user1")
    print(f"   proxy3 沙箱 id = {proxy3.id[:12]}")
    print(f"   还是同一个 proxy 对象吗？ {proxy1 is proxy3}")

    print("6. 验证新沙箱是全新的（note.txt 已不存在）...")
    rd = proxy3.read("/workspace/note.txt")
    print(f"   read note.txt error = {rd.error}")

    print("7. 清理 ...")
    manager.destroy("user1")
    print("Done.")


if __name__ == "__main__":
    main()
