"""验证 SkillsSyncMiddleware 增量同步：首次全量、无变化跳过、变更只传差异。

运行前：只需沙箱 Docker 在跑（不需要 MongoDB / LLM / MCP）。
运行：python test/test_skills_sync.py
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.agent.backends.sandbox_manager import SandboxManager
from src.agent.middlewares import skills_sync as ss


def _manifest(sandbox) -> dict[str, str]:
    resp = sandbox.download_files([ss.MANIFEST_PATH])[0]
    if resp.error or resp.content is None:
        return {}
    return json.loads(resp.content.decode("utf-8"))


def main() -> None:
    sm = SandboxManager()
    sandbox = sm.get_sandbox("default_user")

    with tempfile.TemporaryDirectory() as tmp:
        # 临时技能目录，避免污染真实 skills/
        ss.SKILLS_DIR = Path(tmp)
        base = Path(tmp) / "procurement" / "procurement-analysis"
        base.mkdir(parents=True)
        f1 = base / "SKILL.md"
        f1.write_text("---\nname: procurement-analysis\ndescription: 测试\n---\n流程", encoding="utf-8")
        f2 = Path(tmp) / "procurement" / "helper.md"
        f2.write_text("helper-v1", encoding="utf-8")

        n1 = ss.sync_skills_incremental(sandbox)
        print(f"1) 首次同步上传 {n1} 个文件（应为 2）")

        n2 = ss.sync_skills_incremental(sandbox)
        print(f"2) 无变化再同步 {n2} 个文件（应为 0）")

        f2.write_text("helper-v2", encoding="utf-8")
        n3 = ss.sync_skills_incremental(sandbox)
        print(f"3) 改动一个文件后同步 {n3} 个文件（应为 1）")

        f3 = Path(tmp) / "procurement" / "new.md"
        f3.write_text("new", encoding="utf-8")
        n4 = ss.sync_skills_incremental(sandbox)
        print(f"4) 新增一个文件后同步 {n4} 个文件（应为 1）")

        m = _manifest(sandbox)
        print(f"\nmanifest 条目数：{len(m)}（应为 3）")

    print("\nDone.")


if __name__ == "__main__":
    main()
