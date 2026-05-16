from __future__ import annotations

from pathlib import Path, PurePosixPath

from intranet_side.info_extract.config import PipelineConfig
from intranet_side.info_extract.ftp_get.ftp_client import FtpSession
from intranet_side.info_extract.runtime_logging import build_stage_logger


def pull_articles(config: PipelineConfig) -> int:
    inbox = config.ftp_remote.local_inbox_dir
    archive = config.ftp_remote.local_archive_dir
    logger = build_stage_logger(config.intranet_logs_dir, "ftp_pull")
    inbox.mkdir(parents=True, exist_ok=True)
    archive.mkdir(parents=True, exist_ok=True)
    logger.log(f"[pull] start ftp pull host={config.ftp_remote.host}:{config.ftp_remote.port} remote_base_dir={config.ftp_remote.remote_base_dir}")
    logger.log(f"[pull] local inbox={inbox}")
    pulled = 0
    with FtpSession(config.ftp_remote) as session:
        remote_files = session.list_remote_files(config.ftp_remote.remote_base_dir)
        logger.log(f"[pull] remote files discovered={len(remote_files)}")
        for remote_file in remote_files:
            rel = PurePosixPath(remote_file).relative_to(PurePosixPath(config.ftp_remote.remote_base_dir))
            local_path = inbox / Path(str(rel))
            local_path.parent.mkdir(parents=True, exist_ok=True)
            logger.log(f"[pull] downloading remote_file={remote_file} -> local_path={local_path}")
            session.download_file(remote_file, str(local_path))
            pulled += 1
            if config.ftp_remote.delete_remote_after_download:
                logger.log(f"[pull] delete remote after download remote_file={remote_file}")
                session.remove_remote_file(remote_file)
    logger.log(f"[pull] completed pulled={pulled}")
    return pulled
