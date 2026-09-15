"""网页搜索与抓取工具（Tavily）。

采购研究员用它们从互联网抓商品/供应商信息、查报价、做对比分析。
"""
from __future__ import annotations

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field
from tavily import TavilyClient

from ..config import settings


def _client() -> TavilyClient:
    return TavilyClient(api_key=settings.TAVILY_API_KEY)


class _WebSearchArgs(BaseModel):
    query: str = Field(description="搜索关键词，例如「精密轴承 报价」")
    max_results: int = Field(default=5, description="返回结果条数，默认 5")


def _web_search(query: str, max_results: int = 5) -> str:
    """搜索互联网，返回相关网页的标题、URL 和内容摘要。"""
    result = _client().search(query=query, search_depth="basic", max_results=max_results)
    items = result.get("results", [])
    if not items:
        return (
            "[搜索无结果] Tavily 未返回任何匹配页面。"
            "请如实告知用户当前没有搜到相关信息，不要编造、臆测或引用不存在的网页；"
            "可建议用户换更简短的关键词或英文关键词后重试。"
        )
    lines = []
    for r in items:
        lines.append(
            f"标题: {r.get('title', '')}\n"
            f"URL: {r.get('url', '')}\n"
            f"摘要: {r.get('content', '')}"
        )
    return "\n\n".join(lines)


class _WebFetchArgs(BaseModel):
    url: str = Field(description="要抓取正文的网页 URL")


def _web_fetch(url: str) -> str:
    """抓取指定网页的正文内容。"""
    result = _client().extract(urls=[url])
    items = result.get("results", [])
    if not items:
        return "[抓取失败] 无法读取该页面内容。请如实告知用户，不要编造页面内容。"
    return items[0].get("raw_content", "") or items[0].get("content", "")


web_search = StructuredTool.from_function(
    name="web_search",
    description=(
        "在互联网上搜索信息（商品报价、供应商信息、评测、行情等），"
        "返回相关网页的标题、URL 和内容摘要。用于需要外部信息支撑采购决策时。"
    ),
    func=_web_search,
    args_schema=_WebSearchArgs,
    infer_schema=False,
)

web_fetch = StructuredTool.from_function(
    name="web_fetch",
    description=(
        "抓取指定网页的正文内容。先 web_search 找到目标页面，"
        "再用它读取某个页面的详细信息。"
    ),
    func=_web_fetch,
    args_schema=_WebFetchArgs,
    infer_schema=False,
)
