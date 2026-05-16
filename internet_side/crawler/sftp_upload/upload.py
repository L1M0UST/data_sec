from __future__ import annotations

from pathlib import PurePosixPath

from intranet_side.info_extract.config import PipelineConfig
from intranet_side.info_extract.ftp_get.sftp_client import SftpSession
from intranet_side.info_extract.runtime_logging import build_stage_logger


def upload_articles(config: PipelineConfig) -> int:
    base_dir = config.upload_from_dir
    logger = build_stage_logger(config.internet_logs_dir, "sftp_upload")
    if not base_dir.exists():
        logger.log(f"[upload] skipped because upload_from_dir does not exist path={base_dir}")
        return 0
    logger.log(f"[upload] start upload_from_dir={base_dir} remote_base_dir={config.upload_remote.remote_base_dir}")
    uploaded = 0
    with SftpSession(config.upload_remote) as session:
        for path in sorted(base_dir.rglob("*.md")):
            rel = path.relative_to(base_dir)
            remote_path = str(PurePosixPath(config.upload_remote.remote_base_dir) / PurePosixPath(rel.as_posix()))
            logger.log(f"[upload] uploading local_file={path} -> remote_path={remote_path}")
            session.upload_file(str(path), remote_path)
            path.unlink()
            logger.log(f"[upload] upload success and local deleted path={path}")
            uploaded += 1
    logger.log(f"[upload] completed uploaded={uploaded}")
    return uploaded
