"""记忆更新中间件（中间件矩阵 #6）。

每次 Agent 运行结束后（aafter_agent），用 LLM 从这轮对话里提取
{suppliers, query}，把「最近供应商 + 最近查询」自动合并进
/memories/{user_id}/preferences.md，跨会话保留。

自动更新路径：
  对话结束 → MemoryUpdateMiddleware.aafter_agent()
  → LLM 提取 {suppliers, query} → store 写入 → 跨会话保留。

preferences.md 采用单行 `key: value` 格式：
  preferred_* 字段由「手动路径」（Agent edit_file）维护；
  recent_suppliers / recent_queries 由本中间件自动维护。
"""
from __future__ import annotations

import json
from typing import Any

from langchain.agents.middleware.types import AgentMiddleware
from langchain_core.messages import HumanMessage

from ..log_utils import get_logger

logger = get_logger(__name__)

PREFERENCES_PATH = "/memories/{user_id}/preferences.md"

# 「最近」字段最多保留的条数
MAX_RECENT_SUPPLIERS = 5
MAX_RECENT_QUERIES = 5

# 固定输出顺序：手动维护的 preferred_* 在前，自动维护的 recent_* 在后
FIELD_ORDER = (
    "preferred_output",
    "preferred_chart_type",
    "preferred_currency",
    "preferred_language",
    "recent_suppliers",
    "recent_queries",
)

# 首次运行（该用户还没有 preferences.md）时写入的默认模板
DEFAULT_PREFERENCES = """\
# 用户偏好记忆

preferred_output: 简洁摘要
preferred_chart_type: bar
preferred_currency: CNY
preferred_language: zh-CN
recent_suppliers:
recent_queries:
"""

_EXTRACT_PROMPT = """你是采购领域专家助手的记忆提取器。从下面的对话里提取两类信息：

1. suppliers：对话中出现的供应商名称列表（字符串数组）。没有就返回空数组 []。
2. query：用户本次最核心的采购查询意图，用一句话概括（字符串）。纯闲聊没有采购查询就返回空字符串 ""。

只输出一个 JSON 对象，不要输出任何解释或多余文字。格式示例：
{{"suppliers": ["供应商A", "供应商B"], "query": "查询某物料的库存情况"}}

对话：
{conversation}
"""


def _parse_json(text: str) -> dict[str, Any]:
    """从 LLM 返回的文本里稳健地解析出 JSON 对象。"""
    text = text.strip()
    if text.startswith("```"):
        # 去掉可能的 markdown 代码块围栏
        text = text.strip("`").strip()
        if text.startswith("json"):
            text = text[4:].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # 兜底：截取第一个 { 到最后一个 } 之间的内容再试一次
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                pass
        logger.warning("[MemoryUpdate] LLM 返回无法解析的 JSON：%s", text[:200])
        return {"suppliers": [], "query": ""}


def _parse_preferences(text: str) -> dict[str, str]:
    """把 preferences.md 的 `key: value` 行解析成 dict。"""
    fields: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()
    return fields


def _serialize_preferences(fields: dict[str, str]) -> str:
    """把字段 dict 按固定顺序序列化回 markdown。未知字段追加在末尾保留。"""
    lines = ["# 用户偏好记忆", ""]
    for key in FIELD_ORDER:
        lines.append(f"{key}: {fields.get(key, '')}")
    for key, value in fields.items():
        if key not in FIELD_ORDER:
            lines.append(f"{key}: {value}")
    lines.append("")
    return "\n".join(lines)


def _merge_recent(existing: str, new_items: list[str], limit: int) -> str:
    """把新条目追加到已有的逗号分隔列表里，去重后保留最近 limit 条。"""
    current = [s.strip() for s in existing.split(",") if s.strip()]
    for item in new_items:
        item = (item or "").strip()
        if item and item not in current:
            current.append(item)
    return ", ".join(current[-limit:])


def _merge_fields(existing: str, suppliers: list[str], query: str) -> str:
    """合并：在现有偏好上更新 recent_suppliers / recent_queries。"""
    fields = _parse_preferences(existing)
    fields["recent_suppliers"] = _merge_recent(
        fields.get("recent_suppliers", ""), suppliers, MAX_RECENT_SUPPLIERS
    )
    fields["recent_queries"] = _merge_recent(
        fields.get("recent_queries", ""), [query], MAX_RECENT_QUERIES
    )
    return _serialize_preferences(fields)


def _extract(llm, conversation: str) -> dict[str, Any]:
    prompt = _EXTRACT_PROMPT.format(conversation=conversation)
    resp = llm.invoke(prompt)
    text = resp.content if isinstance(resp.content, str) else str(resp.content)
    return _parse_json(text)


async def _aextract(llm, conversation: str) -> dict[str, Any]:
    prompt = _EXTRACT_PROMPT.format(conversation=conversation)
    resp = await llm.ainvoke(prompt)
    text = resp.content if isinstance(resp.content, str) else str(resp.content)
    return _parse_json(text)


class MemoryUpdateMiddleware(AgentMiddleware):
    """每次 Agent 运行结束后，自动把最近供应商 / 查询持久化到 MongoDB。"""

    def __init__(self, llm, backend, user_id: str) -> None:
        self._llm = llm
        self._backend = backend
        self._user_id = user_id

    def _path(self) -> str:
        return PREFERENCES_PATH.format(user_id=self._user_id)

    @staticmethod
    def _build_conversation(messages: list[Any]) -> str:
        """把最近的对话消息拼成纯文本，供 LLM 提取。只看最近 20 条。"""
        parts: list[str] = []
        for m in messages[-20:]:
            role = getattr(m, "type", None) or getattr(m, "role", "unknown")
            content = getattr(m, "content", "")
            if isinstance(content, list):
                content = " ".join(
                    b.get("text", "") for b in content if isinstance(b, dict)
                )
            content = (content or "").strip()
            if content:
                parts.append(f"{role}: {content}")
        return "\n".join(parts)

    def _read_existing(self) -> str:
        resp = self._backend.download_files([self._path()])[0]
        if resp.error or resp.content is None:
            return ""
        return resp.content.decode("utf-8")

    def _persist(self, extracted: dict[str, Any]) -> None:
        suppliers = extracted.get("suppliers") or []
        query = (extracted.get("query") or "").strip()
        if not suppliers and not query:
            return
        existing = self._read_existing() or DEFAULT_PREFERENCES
        merged = _merge_fields(existing, suppliers, query)
        self._backend.write(self._path(), merged)
        logger.info(
            "[MemoryUpdate] 已更新偏好记忆：suppliers=%s, query=%s", suppliers, query
        )

    def _update(self, messages: list[Any]) -> None:
        if not any(isinstance(m, HumanMessage) for m in messages):
            return
        conversation = self._build_conversation(messages)
        self._persist(_extract(self._llm, conversation))

    async def _aupdate(self, messages: list[Any]) -> None:
        if not any(isinstance(m, HumanMessage) for m in messages):
            return
        conversation = self._build_conversation(messages)
        self._persist(await _aextract(self._llm, conversation))

    def after_agent(self, state: Any, runtime: Any) -> dict[str, Any] | None:
        self._update(state.get("messages", []))
        return None

    async def aafter_agent(self, state: Any, runtime: Any) -> dict[str, Any] | None:
        await self._aupdate(state.get("messages", []))
        return None
