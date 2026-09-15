"""主 Agent 入口：构建 LLM、加载工具、注入中间件，创建 DeepAgent。

在这里把百炼 LLM、MCP 工具、HITL 人工审批、子智能体、中间件栈、沙箱、
记忆等 Harness 能力组装成一个完整的采购领域专家智能助手。
"""
from __future__ import annotations

from langchain_openai import ChatOpenAI
from langchain.agents.middleware import (
    ModelCallLimitMiddleware,
    TodoListMiddleware,
    ToolCallLimitMiddleware,
)
from deepagents import create_deep_agent
from deepagents.middleware.skills import SkillsMiddleware
from deepagents.middleware.summarization import create_summarization_tool_middleware

from .backends.sandbox_manager import SandboxManager
from .backends.backend_factory import build_backend
from .config import settings
from .log_utils import get_logger
from .middlewares.context_injection import ContextInjectionMiddleware
from .middlewares.memory_update import MemoryUpdateMiddleware
from .middlewares.sandbox_breaker import SandboxCircuitBreakerMiddleware
from .middlewares.sandbox_health import SandboxHealthMiddleware
from .middlewares.skills_sync import SkillsSyncMiddleware
from .middlewares.user_skills_restore import UserSkillsRestoreMiddleware
from .subagents import build_subagents
from .tools.chart_tool import build_make_chart_tool
from .tools.hitl_tools import request_order_info
from .tools.mcp_client import load_mcp_tools
from .tools.skill_install_tools import build_install_skill_tool
from .tools.web_tools import web_fetch, web_search

logger = get_logger(__name__)

SYSTEM_PROMPT = (
    "你是采购领域专家智能助手，既具备通用能力（联网搜索、数据分析、代码执行、文档写作），"
    "也精通采购业务。你有两个专职子智能体："
    "1) 采购研究员（procurement-researcher）：从互联网抓取商品/供应商信息，"
    "做「买哪个好」的对比分析并生成采购调研报告；"
    "2) 采购执行员（procurement-executor）：查询/生成/修改采购订单、直接下单，"
    "并查询物料、供应商与 ERP 库存。"
    "判断用户意图后，用 task 工具把活派给对应的子智能体，只向用户转达它们返回的结论。"
    "下单/改单等写操作若缺少必填字段（物料编号 part_id、数量 quantity），"
    "必须调用 request_order_info 工具向用户补齐信息，不要直接在回复里询问；"
    "信息齐全后再调用 order_create、order_update 或 order_place。"
    "当用户提供一个网址并要求「安装/存成技能」时，调用 install_skill 工具。"
    "把调研任务派给采购研究员时，必须把物料的完整信息（编号、名称、规格、当前库存、"
    "预警阈值）一并写进 task 描述，不要只传物料编号；研究员没有 ERP 数据权限，"
    "只拿到编号无法判断要调研什么商品。"
)

# 第 2 层中断：最终审批。创建/更新/下单这类写操作，执行前必须人工批准。
HITL_INTERRUPT_ON = {
    "order_create": {"allowed_decisions": ["approve", "reject"]},
    "order_update": {"allowed_decisions": ["approve", "reject"]},
    "order_place": {"allowed_decisions": ["approve", "reject"]},
}


def _build_llm() -> ChatOpenAI:
    if not settings.LLM_API_KEY:
        raise RuntimeError(
            "未检测到 LLM API Key。请在系统环境变量设置 DASHSCOPE_API_KEY "
            "（或 OPENAI_API_KEY），或在 .env 里设置 LLM_API_KEY。"
        )
    return ChatOpenAI(
        model=settings.LLM_MODEL,
        base_url=settings.LLM_BASE_URL,
        api_key=settings.LLM_API_KEY,
        temperature=0,
        streaming=True,
    )


async def create_main_agent(checkpointer=None):
    """创建主 Agent（DeepAgent），注入 MCP 工具 + HITL + 三层路由文件系统。

    checkpointer 用于支撑 HITL 中断的「存档与恢复」。只有需要中断功能时才传，
    默认不传（普通对话/分析场景不需要）。
    """
    llm = _build_llm()
    tools = await load_mcp_tools()
    tools.append(request_order_info)
    tools.extend([web_search, web_fetch])
    sandbox_manager = SandboxManager()
    tools.append(build_install_skill_tool(llm, sandbox_manager, "default_user"))
    tools.append(build_make_chart_tool(sandbox_manager, "default_user"))
    sandbox = sandbox_manager.get_sandbox("default_user")
    backend = build_backend(sandbox)
    agent = create_deep_agent(
        model=llm,
        system_prompt=SYSTEM_PROMPT,
        tools=tools,
        middleware=[
            # #7 熔断器必须先于健康检查执行，才能拦下「持续故障」快速失败。
            SandboxCircuitBreakerMiddleware(sandbox_manager, "default_user"),
            # #1 健康检查/重建：熔断器放行后，这里确保沙箱活着。
            SandboxHealthMiddleware(sandbox_manager, "default_user"),
            # #2 上下文注入：把用户偏好记忆注入 system prompt。
            ContextInjectionMiddleware(backend, "default_user"),
            SkillsSyncMiddleware(sandbox_manager, "default_user"),
            UserSkillsRestoreMiddleware(sandbox_manager, "default_user", backend),
            SkillsMiddleware(
                backend=backend,
                sources=["/skills/research/", "/skills/execution/", "/skills/installed/"],
            ),
            TodoListMiddleware(),
            # #5 主动压缩：给 Agent 一个 compact_conversation 工具，与内置的
            # 被动摘要（85% 自动压缩）形成「主动 + 被动」两层压缩。
            create_summarization_tool_middleware(llm, backend),
            # #6 记忆更新：对话结束后自动把最近供应商/查询持久化到 MongoDB。
            MemoryUpdateMiddleware(llm, backend, "default_user"),
            # #8/#9 调用限制：LangChain 内置，防止 Agent 死循环（超限优雅结束）。
            ModelCallLimitMiddleware(run_limit=30, exit_behavior="end"),
            ToolCallLimitMiddleware(run_limit=50, exit_behavior="end"),
        ],
        backend=backend,
        subagents=build_subagents(tools),
        interrupt_on=HITL_INTERRUPT_ON,
        checkpointer=checkpointer,
    )
    logger.info(
        "主 Agent 已创建，model=%s, tools=%d", settings.LLM_MODEL, len(tools)
    )
    return agent
