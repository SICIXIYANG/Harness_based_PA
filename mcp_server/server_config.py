"""MCP Server 配置：ERP 后端地址 + MCP 监听地址。

和主 Agent 共用项目根目录的 .env，读 ERP_BASE_URL / MCP_HOST / MCP_PORT。
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=False)

ERP_BASE_URL: str = os.getenv("ERP_BASE_URL", "http://localhost:8080")
MCP_HOST: str = os.getenv("MCP_HOST", "0.0.0.0")
MCP_PORT: int = int(os.getenv("MCP_PORT", "8001"))
