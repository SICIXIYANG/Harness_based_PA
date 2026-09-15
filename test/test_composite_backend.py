"""验证三层路由文件系统：沙箱 / 记忆 / 技能 三路读写 + 记忆持久化。

运行前：先启动 MongoDB（docker compose up -d）。
运行：python test/test_composite_backend.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.agent.backends.backend_factory import build_backend
from src.agent.backends.sandbox_proxy import SandboxProxy
from src.agent.backends.sandbox_setup import create_sandbox, destroy_sandbox


def main() -> None:
    print("1. 创建沙箱并包装成代理 ...")
    sandbox = create_sandbox()
    proxy = SandboxProxy(sandbox)
    print(f"   沙箱 id = {proxy.id[:12]}")

    print("2. 构建三层路由文件系统 ...")
    backend = build_backend(proxy)

    print("3. 往沙箱层写文件（/workspace/） ...")
    w = backend.write("/workspace/tmp.txt", "临时数据\n")
    print(f"   write error = {w.error}")

    print("4. 往记忆层写文件（/memories/） ...")
    w = backend.write("/memories/user-pref.txt", "用户偏好：只报异常供应商\n")
    print(f"   write error = {w.error}")

    print("5. 往技能层写文件（/persisted-skills/） ...")
    w = backend.write("/persisted-skills/report.md", "# 采购报告模板\n")
    print(f"   write error = {w.error}")

    print("6. 从三个层分别读回来 ...")
    r1 = backend.read("/workspace/tmp.txt")
    r2 = backend.read("/memories/user-pref.txt")
    r3 = backend.read("/persisted-skills/report.md")
    print(f"   沙箱层: {r1.file_data['content']!r}" if r1.file_data else f"   沙箱层 error={r1.error}")
    print(f"   记忆层: {r2.file_data['content']!r}" if r2.file_data else f"   记忆层 error={r2.error}")
    print(f"   技能层: {r3.file_data['content']!r}" if r3.file_data else f"   技能层 error={r3.error}")

    print("7. 列出根目录（应看到 /memories/ 和 /persisted-skills/ 两个虚拟目录） ...")
    ls = backend.ls("/")
    for e in (ls.entries or []):
        print(f"   {e['path']}  is_dir={e['is_dir']}")

    print("8. 模拟沙箱故障重建（验证记忆/技能不丢） ...")
    destroy_sandbox(sandbox)
    new_sandbox = create_sandbox()
    proxy.replace_backend(new_sandbox)
    print(f"   新沙箱 id = {proxy.id[:12]}")
    r = backend.read("/workspace/tmp.txt")
    print(f"   读 /workspace/tmp.txt（应不存在） error = {r.error}")
    r = backend.read("/memories/user-pref.txt")
    print(f"   读 /memories/user-pref.txt（应仍在） content = {r.file_data['content']!r}" if r.file_data else f"   读记忆层 error={r.error}")

    print("9. 清理 ...")
    destroy_sandbox(new_sandbox)
    print("Done.")


if __name__ == "__main__":
    main()
