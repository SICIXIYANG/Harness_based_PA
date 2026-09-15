"""全局配置。

所有配置项优先读系统环境变量，其次读 .env，最后用代码里的默认值。
"""
from __future__ import annotations

import os

from .env_utils import load_env

load_env()


def _get_llm_api_key() -> str:
    # 优先级：DASHSCOPE_API_KEY > OPENAI_API_KEY > .env 的 LLM_API_KEY
    return (
        os.getenv("DASHSCOPE_API_KEY")
        or os.getenv("OPENAI_API_KEY")
        or os.getenv("LLM_API_KEY")
        or ""
    )


class Settings:
    # ===== LLM（阿里云百炼 DashScope，OpenAI 兼容）=====
    LLM_API_KEY: str = _get_llm_api_key()
    LLM_BASE_URL: str = os.getenv(
        "LLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"
    )
    LLM_MODEL: str = os.getenv("LLM_MODEL", "qwen-turbo")

    # ===== MongoDB =====
    MONGO_URI: str = os.getenv("MONGO_URI", "mongodb://admin:admin123@localhost:27017")
    MONGO_DB: str = os.getenv("MONGO_DB", "procurement_agent")

    # ===== ERP 后端 + MCP Server =====
    ERP_BASE_URL: str = os.getenv("ERP_BASE_URL", "http://localhost:8080")
    MCP_HOST: str = os.getenv("MCP_HOST", "0.0.0.0")
    MCP_PORT: int = int(os.getenv("MCP_PORT", "8001"))

    # ===== 沙箱 =====
    SANDBOX_IMAGE: str = os.getenv("SANDBOX_IMAGE", "python:3.11-slim")

    # ===== 网页搜索（Tavily）=====
    TAVILY_API_KEY: str = os.getenv("TAVILY_API_KEY", "")


settings = Settings()
