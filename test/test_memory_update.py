"""验证 MemoryUpdateMiddleware：对话结束后自动把最近供应商/查询写进 preferences.md。

分两部分：
  A. 纯函数单测（不需要任何外部依赖）——合并/去重/截断逻辑。
  B. 集成验证（需 MongoDB + 沙箱 Docker 在跑）——用假 LLM 走真实三层路由，
     确认写进了 MongoDB 的 /memories/default_user/preferences.md。

运行：python test/test_memory_update.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from langchain_core.messages import HumanMessage

from src.agent.backends.backend_factory import build_backend
from src.agent.backends.sandbox_proxy import SandboxProxy
from src.agent.backends.sandbox_setup import create_sandbox, destroy_sandbox
from src.agent.config import settings
from src.agent.middlewares import memory_update as mu


class _FakeResp:
    def __init__(self, content: str) -> None:
        self.content = content


class _FakeLLM:
    """假 LLM：invoke/ainvoke 都返回写死的 JSON，不真调百炼。"""

    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def invoke(self, prompt: str) -> _FakeResp:
        return _FakeResp(json.dumps(self._payload, ensure_ascii=False))

    async def ainvoke(self, prompt: str) -> _FakeResp:
        return _FakeResp(json.dumps(self._payload, ensure_ascii=False))


def test_pure() -> None:
    print("【A. 纯函数单测】")

    # 1. 解析 + 序列化往返
    text = "# 用户偏好记忆\n\npreferred_chart_type: pie\nrecent_suppliers: A, B\n"
    fields = mu._parse_preferences(text)
    assert fields["preferred_chart_type"] == "pie", fields
    assert fields["recent_suppliers"] == "A, B", fields

    # 2. 合并：新供应商去重追加
    merged = mu._merge_fields(text, ["B", "C"], "查询库存")
    assert "recent_suppliers: A, B, C" in merged, merged
    assert "recent_queries: 查询库存" in merged, merged

    # 3. 截断：超过 5 条只留最近 5 条
    many = mu._merge_recent("", [f"S{i}" for i in range(8)], 5)
    assert many == "S3, S4, S5, S6, S7", many

    print("   纯函数单测通过 ✓\n")


def test_integration() -> None:
    print("【B. 集成验证（假 LLM + 真实 MongoDB/沙箱）】")

    sandbox = create_sandbox()
    proxy = SandboxProxy(sandbox)
    backend = build_backend(proxy)

    # 0. 清理旧数据，保证可重复
    backend.delete("/memories/default_user/preferences.md")

    # 1. 第一次更新：提取到 2 个供应商 + 1 个查询
    mw = mu.MemoryUpdateMiddleware(
        _FakeLLM({"suppliers": ["供应商A", "供应商B"], "query": "查询物料库存"}),
        backend,
        "default_user",
    )
    mw._update([HumanMessage(content="帮我查一下供应商A和供应商B的库存")])

    r = backend.read("/memories/default_user/preferences.md")
    assert r.file_data, f"读 preferences.md 失败：{r.error}"
    content = r.file_data["content"]
    print(f"   第一次写入后：\n{content}")
    assert "recent_suppliers: 供应商A, 供应商B" in content, content
    assert "recent_queries: 查询物料库存" in content, content

    # 2. 第二次更新：供应商重复（应去重），新增一个查询（应追加）
    mw2 = mu.MemoryUpdateMiddleware(
        _FakeLLM({"suppliers": ["供应商B", "供应商C"], "query": "分析供应商价格"}),
        backend,
        "default_user",
    )
    mw2._update([HumanMessage(content="供应商C的价格怎么样")])

    r = backend.read("/memories/default_user/preferences.md")
    content = r.file_data["content"]
    print(f"   第二次写入后：\n{content}")
    # 供应商去重后应为 A, B, C（B 不重复）
    assert "recent_suppliers: 供应商A, 供应商B, 供应商C" in content, content
    # 查询追加后应为两条
    assert "recent_queries: 查询物料库存, 分析供应商价格" in content, content

    # 3. 空提取（没有供应商也没有查询）应不写文件
    backend.delete("/memories/default_user/preferences.md")
    mw3 = mu.MemoryUpdateMiddleware(
        _FakeLLM({"suppliers": [], "query": ""}), backend, "default_user"
    )
    mw3._update([HumanMessage(content="你好")])
    r = backend.read("/memories/default_user/preferences.md")
    assert r.file_data is None, "空提取不应写入 preferences.md"
    print("   空提取未写文件 ✓")

    destroy_sandbox(sandbox)
    print("   集成验证通过 ✓\n")


if __name__ == "__main__":
    test_pure()
    test_integration()
    print("Done.")
