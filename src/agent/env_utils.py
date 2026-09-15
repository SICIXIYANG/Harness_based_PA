"""环境变量加载工具。

约定：.env 里的配置是「默认值」，系统环境变量优先级更高（不覆盖）。
"""
from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv

# 项目根目录：src/agent/env_utils.py -> 往上三级就是 D:\harness
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def load_env() -> Path:
    """加载项目根目录的 .env，返回项目根目录。

    override=False 保证系统里已存在的环境变量（如 DASHSCOPE_API_KEY）
    不会被 .env 里的同名键覆盖。
    """
    load_dotenv(PROJECT_ROOT / ".env", override=False)
    return PROJECT_ROOT


def project_root() -> Path:
    return PROJECT_ROOT
