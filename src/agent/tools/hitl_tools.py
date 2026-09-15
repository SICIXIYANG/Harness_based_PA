"""HITL 工具：request_order_info（第 1 层中断——数据补充）。

当创建/更新采购订单缺少必填字段时，agent 调用本工具。
工具内部调用 interrupt() 暂停整个图，把「缺哪些字段」展示给用户，
等用户补充数据后返回。

注意：本工具不在 interrupt_on 名单里，所以它触发的中断不会被
HumanInTheLoopMiddleware 拦截（那是第 2 层审批）。两层是顺序关系。
"""
from __future__ import annotations

from langchain_core.tools import StructuredTool
from langgraph.types import interrupt
from pydantic import BaseModel, Field


class _RequestOrderInfoArgs(BaseModel):
    """request_order_info 的入参。"""

    missing_fields: str = Field(
        description="描述创建或更新订单还缺哪些必填字段，例如：物料编号 part_id、数量 quantity。"
    )


def _request_order_info(missing_fields: str) -> str:
    """触发第 1 层中断，向用户请求补充数据，返回用户补充的文本。"""
    result = interrupt(
        {
            "type": "order_info_request",
            "missing_fields": missing_fields,
        }
    )
    if isinstance(result, dict):
        return result.get("supplement", "")
    return str(result)


request_order_info = StructuredTool.from_function(
    name="request_order_info",
    description=(
        "当创建采购订单(order_create)或更新订单(order_update)缺少必填字段"
        "（如物料编号 part_id、数量 quantity）时，调用本工具向用户请求补充信息。"
        "信息已完整时不要调用。"
    ),
    func=_request_order_info,
    args_schema=_RequestOrderInfoArgs,
    infer_schema=False,
)
