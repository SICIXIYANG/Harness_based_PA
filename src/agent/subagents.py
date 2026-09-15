"""子 Agent 定义。

采购领域专家智能助手有两个专职子 Agent：

1. procurement-researcher —— 采购研究员：用网页搜索/抓取做「买哪个好」的
   对比调研，产出采购调研报告并保存到沙箱文件系统。
2. procurement-executor  —— 采购执行员：查询/生成/修改采购订单、直接下单，
   并查询物料、供应商与 ERP 库存。

主 Agent 通过 `task` 工具把活派给它们，只接收它们返回的精简结论。
两个子 Agent 都会自动获得文件系统工具（write_file / read_file / ls 等），
研究员靠它把报告写入 /workspace/reports/。
"""
from __future__ import annotations

from langchain_core.tools import BaseTool


def _pick(tools: list[BaseTool], *names: str) -> list[BaseTool]:
    """按名字从工具列表里挑出指定工具，保持声明顺序。"""
    by_name = {t.name: t for t in tools}
    return [by_name[n] for n in names if n in by_name]


# 采购执行员可用的 ERP / 订单 / 物料 / 供应商 / 库存工具。
_EXECUTOR_TOOL_NAMES = (
    "order_create",
    "order_update",
    "order_search_details",
    "order_list",
    "order_place",
    "part_query",
    "part_search",
    "part_by_supplier",
    "supplier_query",
    "supplier_create",
    "inventory_query",
    "inventory_warning",
    "request_order_info",
)

# 采购研究员可用的 ERP 只读工具：查现有物料/供应商的报价与评级，作为和网上调研对比的基准。
_RESEARCHER_ERP_TOOL_NAMES = (
    "part_query",
    "part_search",
    "part_by_supplier",
    "supplier_query",
)


def build_subagents(tools: list[BaseTool]) -> list[dict]:
    """返回两个采购领域子 Agent 的定义。

    每个子 Agent 是一个 dict，含 name / description / system_prompt / tools / skills。
    name 是主 Agent 派活时用的唯一标识；description 是主 Agent 判断「何时该派给它」的依据。
    skills 指向沙箱里该子 Agent 专属的技能目录（由 SkillsSyncMiddleware 从本地同步过去）。
    """
    return [
        {
            "name": "procurement-researcher",
            "description": (
                "采购研究员：查询现有物料/供应商的报价与评级，结合互联网搜索做「买哪个好」"
                "的对比分析，并生成采购调研报告保存到 /workspace/reports/ 目录。"
                "当用户需要外部行情、报价、供应商评测等联网调研时派给它。"
            ),
            "system_prompt": (
                "你是采购研究员。收到任务后："
                "1) 若任务涉及「和现有供应商/物料对比」，先用 part_query / part_search / "
                "part_by_supplier / supplier_query 等 ERP 只读工具查出现有供应商的报价、"
                "评级、物料价格，作为对比基准；"
                "2) 用 web_search 搜索候选商品/供应商/行情，必要时用 web_fetch 抓取详情页；"
                "3) 按价格、质量、品牌、供货等维度做对比，给出明确推荐及理由；"
                "4) 用 write_file 把报告保存到 /workspace/reports/report_{时间戳}.md，"
                "并返回报告的保存路径与核心结论。"
                "5) 物料编号（如 P002）是内部编码，若任务里只有编号而没有名称/规格，"
                "说明信息不全，不要拿编号去搜索，直接返回并索要物料名称与规格。"
                "所有结论必须来自 ERP 查询或搜索结果，查不到就如实说，"
                "绝不编造价格、品牌或供应商信息。"
            ),
            "tools": _pick(
                tools, "web_search", "web_fetch", *_RESEARCHER_ERP_TOOL_NAMES
            ),
            "skills": ["/skills/research/"],
        },
        {
            "name": "procurement-executor",
            "description": (
                "采购执行员：查询/生成/修改采购订单、直接下单（扣减库存），"
                "并查询物料、供应商与 ERP 库存。当用户要下单、改单、查库存或查物料时派给它。"
            ),
            "system_prompt": (
                "你是采购执行员。收到任务后："
                "1) 下单/改单等写操作若缺少必填字段（part_id、quantity），"
                "先调用 request_order_info 向用户补齐，不要在回复里直接问；"
                "2) 信息齐全后用 order_create / order_update，直接下单用 order_place；"
                "若下单给 ERP 里还没有的新供应商，先调用 supplier_create 注册拿到编号，"
                "再把编号作为 supplier_id 传给 order_create；"
                "3) 写操作执行前需要人工批准，耐心等待批准结果；"
                "4) 读操作用 part_* / supplier_query / inventory_* / order_* 系列工具。"
                "一切以工具返回为准，不要编造订单号、库存数、物料或供应商编号。"
            ),
            "tools": _pick(tools, *_EXECUTOR_TOOL_NAMES),
            "skills": ["/skills/execution/"],
        },
    ]
