"""沙箱创建 + 环境初始化。

负责创建并启动沙箱容器、初始化工作目录，以及按名字连接 / 销毁沙箱。
"""
from __future__ import annotations

import uuid

import docker

from ..config import settings
from .custom_opensandbox import DockerSandbox


def _docker_client() -> docker.DockerClient:
    return docker.from_env()


def create_sandbox(name: str | None = None) -> DockerSandbox:
    """创建并启动一个沙箱容器，包装成 DockerSandbox 返回。"""
    client = _docker_client()
    container_name = name or f"procurement-sandbox-{uuid.uuid4().hex[:8]}"

    container = client.containers.run(
        image=settings.SANDBOX_IMAGE,
        command="sleep infinity",  # 让容器保持运行，供后续 exec 进入
        detach=True,
        name=container_name,
    )
    # 初始化工作目录
    container.exec_run("mkdir -p /workspace")
    _ensure_chart_env(container)
    return DockerSandbox(container)


def _ensure_chart_env(container) -> None:
    """安装 matplotlib 与中文字体（供 make_chart 画图用），已装则跳过。"""
    if container.exec_run("python -c 'import matplotlib'").exit_code != 0:
        container.exec_run("pip install --no-cache-dir --quiet matplotlib")
    # 无 CJK 字体时中文标签会渲染成方块
    has_cjk = container.exec_run(
        "python -c 'import matplotlib.font_manager as fm; "
        "exit(0 if any(\"CJK\" in f.name for f in fm.fontManager.ttflist) else 1)'"
    )
    if has_cjk.exit_code != 0:
        container.exec_run(
            "apt-get update -qq && apt-get install -y -qq "
            "--no-install-recommends fonts-noto-cjk"
        )


def connect_sandbox(name: str) -> DockerSandbox | None:
    """按名字连接一个已存在的沙箱容器；不存在则返回 None。"""
    client = _docker_client()
    try:
        container = client.containers.get(name)
    except docker.errors.NotFound:
        return None
    return DockerSandbox(container)


def destroy_sandbox(sandbox: DockerSandbox) -> None:
    """删除沙箱容器（强制）。"""
    try:
        sandbox.container.remove(force=True)
    except docker.errors.NotFound:
        pass
