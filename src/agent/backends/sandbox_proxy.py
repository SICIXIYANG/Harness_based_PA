"""沙箱代理层（热替换）。

对外提供一个稳定句柄。上层（Agent / 中间件）始终持有这个 Proxy 对象，
当底层沙箱故障被重建时，只需调用 replace_backend() 换掉内部实现，
上层无感知、无需重新获取引用。
"""
from __future__ import annotations

from deepagents.backends.protocol import (
    ExecuteResponse,
    FileDownloadResponse,
    FileUploadResponse,
)
from deepagents.backends.sandbox import BaseSandbox


class SandboxProxy(BaseSandbox):
    """稳定的沙箱句柄，内部 backend 可热替换。

    继承 BaseSandbox，只实现 4 个抽象方法并委托给内部 backend；
    ls/read/write/edit/glob/grep/delete 走 BaseSandbox 的默认实现，
    它们内部调 self.execute / self.upload_files，因此热替换后自动生效。
    """

    def __init__(self, backend: BaseSandbox) -> None:
        self._backend = backend

    @property
    def backend(self) -> BaseSandbox:
        return self._backend

    def replace_backend(self, backend: BaseSandbox) -> None:
        self._backend = backend

    @property
    def id(self) -> str:
        return self._backend.id

    def execute(self, command: str, *, timeout: int | None = None) -> ExecuteResponse:
        return self._backend.execute(command, timeout=timeout)

    def upload_files(self, files: list[tuple[str, bytes]]) -> list[FileUploadResponse]:
        return self._backend.upload_files(files)

    def download_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        return self._backend.download_files(paths)
