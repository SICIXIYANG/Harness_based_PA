"""历史会话 CRUD（读 display_messages 集合）。"""
from __future__ import annotations

from fastapi import APIRouter

from ..web_config import get_database

router = APIRouter()


@router.get("/api/history")
async def list_sessions():
    """列出所有会话（thread_id + 标题 + 更新时间，按最近排序）。"""
    col = get_database()["display_messages"]
    cursor = col.find({}).sort("_id", 1)
    rows = await cursor.to_list(length=10000)

    sessions: dict[str, dict] = {}
    for row in rows:
        tid = row["thread_id"]
        if tid not in sessions:
            sessions[tid] = {
                "thread_id": tid,
                "title": str(row.get("content", ""))[:30],
                "updated_at": 0,
            }
        sessions[tid]["updated_at"] = int(row["_id"].generation_time.timestamp())

    items = sorted(sessions.values(), key=lambda s: s["updated_at"], reverse=True)
    return {"sessions": items}


@router.get("/api/history/{thread_id}")
async def get_session(thread_id: str):
    """返回某个会话的完整对话（按插入顺序）。"""
    col = get_database()["display_messages"]
    cursor = col.find({"thread_id": thread_id}).sort("_id", 1)
    items = await cursor.to_list(length=1000)
    return {
        "thread_id": thread_id,
        "messages": [{"role": i["role"], "content": i["content"]} for i in items],
    }


@router.delete("/api/history/{thread_id}")
async def delete_session(thread_id: str):
    """删除某个会话的历史。"""
    col = get_database()["display_messages"]
    result = await col.delete_many({"thread_id": thread_id})
    return {"deleted": result.deleted_count}
