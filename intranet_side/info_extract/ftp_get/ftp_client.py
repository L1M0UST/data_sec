from __future__ import annotations

from dataclasses import dataclass
from ftplib import FTP, error_perm
from io import BytesIO
from pathlib import PurePosixPath

from intranet_side.info_extract.config import FtpRemoteConfig


@dataclass(frozen=True)
class RemoteFile:
    path: str
    is_dir: bool


class FtpSession:
    def __init__(self, config: FtpRemoteConfig):
        self.config = config
        self.client: FTP | None = None

    def __enter__(self) -> "FtpSession":
        client = FTP()
        client.connect(self.config.host, self.config.port, timeout=30)
        client.login(self.config.username, self.config.password or "")
        client.encoding = "utf-8"
        self.client = client
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self.client is not None:
            try:
                self.client.quit()
            except Exception:
                self.client.close()

    def _is_dir(self, remote_path: str) -> bool:
        assert self.client is not None
        current = self.client.pwd()
        try:
            self.client.cwd(remote_path)
            self.client.cwd(current)
            return True
        except error_perm:
            return False

    def list_remote_files(self, remote_dir: str) -> list[str]:
        assert self.client is not None
        names = self.client.nlst(remote_dir)
        out: list[str] = []
        for name in names:
            full = name
            if not full.startswith("/") and remote_dir not in {"", "/"}:
                full = str(PurePosixPath(remote_dir) / name)
            if self._is_dir(full):
                out.extend(self.list_remote_files(full))
            else:
                out.append(full)
        return out

    def download_file(self, remote_path: str, local_path: str) -> None:
        assert self.client is not None
        with open(local_path, "wb") as f:
            self.client.retrbinary(f"RETR {remote_path}", f.write)

    def remove_remote_file(self, remote_path: str) -> None:
        assert self.client is not None
        self.client.delete(remote_path)
