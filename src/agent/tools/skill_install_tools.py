"""技能安装工具。

用户给一个网址，Agent 抓取网页内容，用 LLM 提炼成一份符合 Agent Skills
规范的 SKILL.md，写入本地 skills/installed/<name>/ 目录，并立即同步到沙箱，
实现从任意网址自主学习新技能。
"""
from __future__ import annotations

import re
from pathlib import Path

from langchain_core.tools import StructuredTool
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from tavily import TavilyClient

from ..backends.sandbox_manager import SandboxManager
from ..config import settings
from ..env_utils import project_root
from ..middlewares.skills_sync import sync_skills_incremental

SKILL_GROUP = "installed"
MAX_CONTENT_LEN = 12000


def _slugify(name: str) -> str:
    """把任意名字规范成合法的 skill 名（小写字母数字 + 单连字符，≤64 字符）。"""
    s = name.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return (s or "skill")[:64]


def _strip_fence(text: str) -> str:
    """去掉 LLM 可能额外包上的 markdown 代码块围栏。"""
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z]*\s*\n?", "", t)
        t = re.sub(r"\n?```\s*$", "", t)
    return t.strip()


_SKILL_GEN_PROMPT = """你是一个技能提炼器。根据下面的网页内容，生成一份符合 Anthropic Agent Skills 规范的 SKILL.md 文件。

要求：
1. 开头是 YAML frontmatter（用 --- 包裹），包含两个字段：
   - name：技能名，小写英文加连字符，例如 web-research、data-analysis，要简洁概括主题。
   - description：用一句话说明这个技能做什么、什么时候用（中文，80 字以内）。
2. 正文用中文，至少包含三部分：适用场景、标准流程（分步骤）、注意事项。
3. 只输出 SKILL.md 的完整内容，不要任何解释、前缀或代码块围栏。

网页 URL：{url}

网页内容：
{content}
"""


class _InstallSkillArgs(BaseModel):
    url: str = Field(description="要提炼成技能的网页 URL")
    name: str = Field(default="", description="可选，指定技能名（英文），不传则自动生成")


def _gen_skill_md(llm: ChatOpenAI, url: str, content: str) -> str:
    prompt = _SKILL_GEN_PROMPT.format(url=url, content=content)
    resp = llm.invoke(prompt)
    text = getattr(resp, "content", "") or str(resp)
    return _strip_fence(text)


def _parse_name(skill_md: str, fallback: str) -> str:
    """从 frontmatter 里读 name；读不到就用 fallback 规范化。"""
    m = re.search(r"^---\s*\n(.*?)\n---", skill_md, re.DOTALL)
    if m:
        nm = re.search(r"^name:\s*(.+)$", m.group(1), re.MULTILINE)
        if nm:
            return _slugify(nm.group(1))
    return _slugify(fallback)


def _normalize_name(skill_md: str, name: str) -> str:
    """把 frontmatter 里的 name 改成规范化后的值（保证 name == 目录名）。"""
    return re.sub(r"^name:\s*.+$", f"name: {name}", skill_md, count=1, flags=re.MULTILINE)


def build_install_skill_tool(
    llm: ChatOpenAI, sandbox_manager: SandboxManager, user_id: str
) -> StructuredTool:
    """构造 install_skill 工具（闭包捕获 llm 和 sandbox_manager）。"""

    def _install_skill(url: str, name: str = "") -> str:
        # 1. 抓取网页正文
        client = TavilyClient(api_key=settings.TAVILY_API_KEY)
        result = client.extract(urls=[url])
        items = result.get("results", [])
        if not items:
            return "[安装失败] 无法读取该网址内容。请确认网址可公开访问，或换一个网址重试。"
        content = items[0].get("raw_content", "") or items[0].get("content", "")
        if not content.strip():
            return "[安装失败] 网页内容为空，无法提炼技能。"

        content = content[:MAX_CONTENT_LEN]

        # 2. LLM 提炼成 SKILL.md
        skill_md = _gen_skill_md(llm, url, content)
        if not skill_md:
            return "[安装失败] 技能内容生成失败，请重试。"

        # 3. 规范化 name，写本地文件
        skill_name = _parse_name(skill_md, name or url)
        skill_md = _normalize_name(skill_md, skill_name)
        skill_dir: Path = project_root() / "skills" / SKILL_GROUP / skill_name
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text(skill_md, encoding="utf-8")

        # 4. 立即同步到沙箱
        sandbox = sandbox_manager.get_sandbox(user_id)
        n = sync_skills_incremental(sandbox)

        return (
            f"[安装成功] 已安装技能 {skill_name}，"
            f"保存在 skills/{SKILL_GROUP}/{skill_name}/SKILL.md，"
            f"本次同步 {n} 个文件到沙箱。下一轮对话即可使用该技能。"
        )

    return StructuredTool.from_function(
        name="install_skill",
        description=(
            "根据用户提供的网址安装一个新技能：抓取网页内容，用 LLM 提炼成一份"
            "规范的操作手册（SKILL.md），保存到本地技能库并同步到沙箱。"
            "当用户说「按这个网址装个技能」「把这个网页存成技能」等时使用。"
        ),
        func=_install_skill,
        args_schema=_InstallSkillArgs,
        infer_schema=False,
    )
