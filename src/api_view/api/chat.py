"""SSE 流式对话 + 中断恢复。

流格式（基于 langgraph 1.2.11 实测，与 PDF 里写的 `interrupts` 不同）：
- astream(..., stream_mode=["messages", "values"], subgraphs=True)
  产出三元组 (namespace, mode, data)
  - namespace = () 是主图；("子Agent名:taskid",) 是子 Agent
  - mode = "messages" → data = (message, metadata)
  - mode = "values"   → data = 整个 state dict，中断时含 __interrupt__ key
- __interrupt__ 的值形如 (Interrupt, ...)，取 .value 才是真正的中断数据

SSE 事件类型（前端按 type 分支渲染）：
  token       模型输出的一段文本增量
  tool_start  工具开始调用（携带工具名）
  tool_args   工具参数增量（前端累加）
  tool_result 工具返回结果
  interrupt   触发人工介入（第 1 层补数据 / 第 2 层审批）
  done        本轮结束
"""
from __future__ import annotations

import json
import uuid
from typing import Any, AsyncIterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.types import Command
from pydantic import BaseModel

from ...agent.schema import ChatRequest
from ..agent_loader import agent_loader
from ..web_config import get_database

router = APIRouter()


class ResumeRequest(BaseModel):
    """恢复中断的请求。resume 内容透传给 Command：
    第 1 层补数据 → {"supplement": "物料编号 P002，数量 100"}
    第 2 层审批   → {"decisions": [{"type": "approve"}]}
    """

    thread_id: str
    resume: dict[str, Any]


def _sse(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False, default=str)}\n\n"


def _source(namespace: tuple[str, ...]) -> str:
    """把 namespace 转成来源名：空=主 Agent，否则取子 Agent 名。"""
    if not namespace:
        return "main"
    return namespace[0].split(":")[0]


async def _persist(thread_id: str, messages: list[Any]) -> None:
    """把最终 state 里的 user/assistant 文本落库，供历史页读取。"""
    docs = []
    for m in messages:
        if isinstance(m, HumanMessage):
            role = "user"
        elif isinstance(m, AIMessage):
            role = "assistant"
        else:
            continue
        content = m.content
        if not isinstance(content, str):
            content = json.dumps(content, ensure_ascii=False)
        docs.append({"thread_id": thread_id, "role": role, "content": content})
    if not docs:
        return
    col = get_database()["display_messages"]
    await col.delete_many({"thread_id": thread_id})
    await col.insert_many(docs)


async def _stream(input_or_command, config: dict) -> AsyncIterator[str]:
    agent = await agent_loader.get_agent()
    tool_buffers: dict[int, dict[str, str]] = {}
    last_messages: list[Any] = []

    async for chunk in agent.astream(
        input_or_command,
        config=config,
        stream_mode=["messages", "values"],
        subgraphs=True,
    ):
        # 三元组 (namespace, mode, data) / 二元组 (mode, data)
        if len(chunk) == 3:
            namespace, mode, data = chunk
        else:
            namespace, mode, data = (), chunk[0], chunk[1]

        if mode == "messages":
            message, _metadata = data
            src = _source(namespace)

            if isinstance(message, ToolMessage):
                yield _sse({
                    "type": "tool_result",
                    "source": src,
                    "name": getattr(message, "name", ""),
                    "id": getattr(message, "tool_call_id", ""),
                    "content": str(message.content),
                })
                continue

            # AI 消息：文本 token + 工具调用增量
            content = getattr(message, "content", "")
            if content:
                if isinstance(content, str):
                    text = content
                else:
                    text = "".join(
                        c.get("text", "") if isinstance(c, dict) else str(c)
                        for c in content
                    )
                if text:
                    yield _sse({"type": "token", "source": src, "content": text})

            for tc in getattr(message, "tool_call_chunks", None) or []:
                idx = tc.get("index", 0)
                buf = tool_buffers.setdefault(idx, {"name": "", "args": ""})
                if tc.get("name") and not buf["name"]:
                    buf["name"] = tc["name"]
                    yield _sse({
                        "type": "tool_start",
                        "source": src,
                        "name": tc["name"],
                        "index": idx,
                        "id": tc.get("id", ""),
                    })
                if tc.get("args"):
                    buf["args"] += tc["args"]
                    yield _sse({
                        "type": "tool_args",
                        "source": src,
                        "index": idx,
                        "args": tc["args"],
                    })

        elif mode == "values":
            if "__interrupt__" in data:
                for it in data["__interrupt__"]:
                    yield _sse({"type": "interrupt", "value": it.value})
            last_messages = data.get("messages", last_messages)

    await _persist(config["configurable"]["thread_id"], last_messages)
    yield _sse({"type": "done"})


@router.post("/api/chat")
async def chat(req: ChatRequest):
    thread_id = req.thread_id or uuid.uuid4().hex
    config = agent_loader.create_config(thread_id)
    return StreamingResponse(
        _stream({"messages": [{"role": "user", "content": req.message}]}, config),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/api/chat/resume")
async def resume(req: ResumeRequest):
    config = agent_loader.create_config(req.thread_id)
    return StreamingResponse(
        _stream(Command(resume=req.resume), config),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
