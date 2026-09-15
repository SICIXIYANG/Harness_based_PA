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
    return DockerSandbox(container)


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
