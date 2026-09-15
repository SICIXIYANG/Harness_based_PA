"""数据模型。"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """前端发起的对话请求。"""

    message: str
    thread_id: Optional[str] = None


class UserPreferences(BaseModel):
    """用户偏好（持久化在 /memories/{user_id}/preferences.md）。"""

    preferred_output: Optional[str] = None
    preferred_chart_type: Optional[str] = None
    preferred_currency: Optional[str] = None
    preferred_language: Optional[str] = None
    recent_suppliers: list[str] = Field(default_factory=list)
    recent_queries: list[str] = Field(default_factory=list)


class ProcurementContext(BaseModel):
    """注入到 Agent 运行时的用户上下文。"""

    user_id: str = "default_user"
    username: Optional[str] = None
    preferences: Optional[UserPreferences] = None
    extra: dict[str, Any] = Field(default_factory=dict)
