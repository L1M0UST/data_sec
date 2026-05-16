from __future__ import annotations

from pathlib import PurePosixPath
import stat

import paramiko

from intranet_side.info_extract.config import UploadRemoteConfig


class SftpSession:
    def __init__(self, config: UploadRemoteConfig):
        self.config = config
        self.transport: paramiko.Transport | None = None
        self.client: paramiko.SFTPClient | None = None

    def __enter__(self) -> "SftpSession":
        transport = paramiko.Transport((self.config.host, self.config.port))
        if self.config.private_key_path:
            pkey = paramiko.RSAKey.from_private_key_file(self.config.private_key_path)
            transport.connect(username=self.config.username, pkey=pkey)
        else:
            transport.connect(username=self.config.username, password=self.config.password)
        self.transport = transport
        self.client = paramiko.SFTPClient.from_transport(transport)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self.client is not None:
            self.client.close()
        if self.transport is not None:
            self.transport.close()

    def ensure_remote_dir(self, remote_dir: str) -> None:
        assert self.client is not None
        path = PurePosixPath(remote_dir)
        current = PurePosixPath("/") if path.is_absolute() else PurePosixPath(".")
        for part in path.parts:
            if part in {"/", "."}:
                continue
            current = current / part
            try:
                self.client.stat(str(current))
            except FileNotFoundError:
                self.client.mkdir(str(current))

    def upload_file(self, local_path: str, remote_path: str) -> None:
        assert self.client is not None
        remote_parent = str(PurePosixPath(remote_path).parent)
        self.ensure_remote_dir(remote_parent)
        self.client.put(local_path, remote_path)
        st = self.client.stat(remote_path)
        if st.st_size <= 0:
            raise RuntimeError(f"upload verification failed: {remote_path}")

    def download_file(self, remote_path: str, local_path: str) -> None:
        assert self.client is not None
        self.client.get(remote_path, local_path)

    def list_remote_files(self, remote_dir: str) -> list[str]:
        assert self.client is not None
        out: list[str] = []
        for entry in self.client.listdir_attr(remote_dir):
            name = entry.filename
            full = str(PurePosixPath(remote_dir) / name)
            if stat.S_ISDIR(entry.st_mode):
                out.extend(self.list_remote_files(full))
            else:
                out.append(full)
        return out

    def remove_remote_file(self, remote_path: str) -> None:
        assert self.client is not None
        self.client.remove(remote_path)
