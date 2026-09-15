"""验证 Docker 沙箱基本能力。

运行前请确认：
1. Docker Desktop 已启动（docker ps 能列出）
2. 已安装 docker 包（pip show docker）

运行：python test/test_sandbox.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.agent.backends.sandbox_setup import create_sandbox, destroy_sandbox


def main() -> None:
    print("1. 创建沙箱容器 ...")
    sandbox = create_sandbox()
    print(f"   沙箱 ID: {sandbox.id[:12]}")

    print("2. 执行 shell 命令 echo ...")
    r = sandbox.execute("echo hello-from-sandbox")
    print(f"   exit_code={r.exit_code}  output={r.output.strip()!r}")

    print("3. 执行 Python 代码 ...")
    r = sandbox.execute("python3 -c 'print(1 + 2)'")
    print(f"   exit_code={r.exit_code}  output={r.output.strip()!r}")

    print("4. 写文件再读回来 ...")
    w = sandbox.write("/workspace/test.txt", "hello procurement\n")
    print(f"   write: path={w.path}  error={w.error}")
    rd = sandbox.read("/workspace/test.txt")
    if rd.file_data is not None:
        print(f"   read: content={rd.file_data['content']!r}  error={rd.error}")
    else:
        print(f"   read: error={rd.error}")

    print("5. 列出目录内容 ...")
    ls = sandbox.ls("/workspace")
    print(f"   ls: error={ls.error}  entries={[e['path'] for e in (ls.entries or [])]}")

    print("6. 清理沙箱容器 ...")
    destroy_sandbox(sandbox)
    print("Done.")


if __name__ == "__main__":
    main()
