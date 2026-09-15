"""MongoDB 连接（motor 异步驱动）。

display_messages 集合存「给人看的对话历史」（user / assistant 文本），
供前端历史页和后续回放调试器读取。
"""
from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from ..agent.config import settings

_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None


def get_database() -> AsyncIOMotorDatabase:
    """懒加载 MongoDB 客户端，返回数据库句柄。"""
    global _client, _db
    if _db is None:
        _client = AsyncIOMotorClient(settings.MONGO_URI)
        _db = _client[settings.MONGO_DB]
    return _db


def close_database() -> None:
    """关闭连接（FastAPI shutdown 时调用）。"""
    global _client, _db
    if _client is not None:
        _client.close()
        _client = None
        _db = None
