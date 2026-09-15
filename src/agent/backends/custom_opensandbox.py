"""自定义 Docker 沙箱 backend（DockerSandbox）。

继承 deepagents 的 `BaseSandbox`。`BaseSandbox` 已经用 `execute` / `upload_files`
实现了 `ls` / `read` / `write` / `edit` / `glob` / `grep` / `delete` 及异步版本，
所以这里只需实现 4 个核心方法：

1. `execute`         —— 在容器里执行命令
2. `upload_files`    —— 把文件上传进容器
3. `download_files`  —— 从容器下载文件
4. `id`              —— 沙箱唯一标识
"""
from __future__ import annotations

import io
import tarfile

import docker
from deepagents.backends.protocol import (
    ExecuteResponse,
    FileDownloadResponse,
    FileUploadResponse,
)
from deepagents.backends.sandbox import BaseSandbox


class DockerSandbox(BaseSandbox):
    """把一个运行中的 Docker 容器包装成 deepagents 的沙箱 backend。"""

    def __init__(self, container: docker.models.containers.Container) -> None:
        self.container = container

    @property
    def id(self) -> str:
        return self.container.id

    def execute(self, command: str, *, timeout: int | None = None) -> ExecuteResponse:
        exit_code, output = self.container.exec_run(
            command,
            stdout=True,
            stderr=True,
            demux=False,
        )
        if isinstance(output, bytes):
            text = output.decode("utf-8", errors="replace")
        else:
            text = str(output)
        return ExecuteResponse(output=text, exit_code=exit_code)

    def upload_files(self, files: list[tuple[str, bytes]]) -> list[FileUploadResponse]:
        # 把多个 (path, content) 打包成一个 tar 流，一次性 put_archive 进容器
        tar_stream = io.BytesIO()
        with tarfile.open(fileobj=tar_stream, mode="w") as tar:
            for path, content in files:
                info = tarfile.TarInfo(name=path.lstrip("/"))
                info.size = len(content)
                tar.addfile(info, io.BytesIO(content))
        tar_stream.seek(0)

        try:
            self.container.put_archive("/", tar_stream)
        except Exception as exc:  # noqa: BLE001
            return [FileUploadResponse(path=p, error=str(exc)) for p, _ in files]
        return [FileUploadResponse(path=p) for p, _ in files]

    def download_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        responses: list[FileDownloadResponse] = []
        for path in paths:
            try:
                bits, _ = self.container.get_archive(path)
                responses.append(
                    FileDownloadResponse(
                        path=path, content=_extract_tar_file(_stream_to_bytes(bits))
                    )
                )
            except Exception as exc:  # noqa: BLE001
                responses.append(FileDownloadResponse(path=path, error=str(exc)))
        return responses


def _stream_to_bytes(stream) -> bytes:
    """把 get_archive 返回的 tar 字节流转成 bytes。"""
    if hasattr(stream, "read"):
        data = stream.read()
        if isinstance(data, str):
            return data.encode("utf-8")
        return data
    return b"".join(stream)


def _extract_tar_file(tar_bytes: bytes) -> bytes:
    """get_archive 返回的是 tar 归档，这里解出里面第一个普通文件的内容。"""
    with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r:") as tar:
        for member in tar.getmembers():
            if member.isfile():
                f = tar.extractfile(member)
                if f is not None:
                    return f.read()
    return b""
