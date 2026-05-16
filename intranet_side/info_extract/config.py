from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class UploadRemoteConfig:
    host: str
    port: int
    username: str
    password: str | None
    private_key_path: str | None
    remote_base_dir: str


@dataclass(frozen=True)
class FtpRemoteConfig:
    host: str
    port: int
    username: str
    password: str | None
    remote_base_dir: str
    local_inbox_dir: Path
    local_archive_dir: Path
    delete_remote_after_download: bool


@dataclass(frozen=True)
class LlmConfig:
    endpoint: str
    api_key: str | None
    model: str
    timeout_seconds: float
    max_input_chars: int


@dataclass(frozen=True)
class ClickHouseConfig:
    host: str
    port: int
    username: str
    password: str
    database: str
    table: str
    secure: bool


@dataclass(frozen=True)
class PipelineConfig:
    crawler_config_path: Path
    upload_from_dir: Path
    state_db_path: Path
    upload_remote: UploadRemoteConfig
    ftp_remote: FtpRemoteConfig
    llm: LlmConfig
    clickhouse: ClickHouseConfig
    processed_dir: Path
    failed_dir: Path
    internet_logs_dir: Path
    intranet_logs_dir: Path


def _get_path(data: dict[str, Any], key: str, default: str) -> Path:
    return Path(data.get(key, default))


def load_pipeline_config(path: Path) -> PipelineConfig:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    upload_remote = data.get("upload_remote", {})
    ftp_remote = data.get("ftp_remote", {})
    llm = data.get("llm", {})
    clickhouse = data.get("clickhouse", {})
    return PipelineConfig(
        crawler_config_path=Path(data.get("crawler_config_path", "sites.yaml")),
        upload_from_dir=_get_path(data, "upload_from_dir", "data/internet_side/crawler_output/articles"),
        state_db_path=_get_path(data, "state_db_path", "data/internet_side/crawler_state/state.db"),
        upload_remote=UploadRemoteConfig(
            host=upload_remote.get("host", ""),
            port=int(upload_remote.get("port", 22)),
            username=upload_remote.get("username", ""),
            password=upload_remote.get("password"),
            private_key_path=upload_remote.get("private_key_path"),
            remote_base_dir=upload_remote.get("remote_base_dir", "/data_sec/internet_side/upload_articles"),
        ),
        ftp_remote=FtpRemoteConfig(
            host=ftp_remote.get("host", ""),
            port=int(ftp_remote.get("port", 21)),
            username=ftp_remote.get("username", ""),
            password=ftp_remote.get("password"),
            remote_base_dir=ftp_remote.get("remote_base_dir", "/data_sec/internet_side/upload_articles"),
            local_inbox_dir=Path(ftp_remote.get("local_inbox_dir", "data/intranet_side/ftp_stage/inbox")),
            local_archive_dir=Path(ftp_remote.get("local_archive_dir", "data/intranet_side/ftp_stage/archive")),
            delete_remote_after_download=bool(ftp_remote.get("delete_remote_after_download", True)),
        ),
        llm=LlmConfig(
            endpoint=llm.get("endpoint", ""),
            api_key=llm.get("api_key"),
            model=llm.get("model", "qwen-plus"),
            timeout_seconds=float(llm.get("timeout_seconds", 120)),
            max_input_chars=int(llm.get("max_input_chars", 12000)),
        ),
        clickhouse=ClickHouseConfig(
            host=clickhouse.get("host", ""),
            port=int(clickhouse.get("port", 8123)),
            username=clickhouse.get("username", "default"),
            password=clickhouse.get("password", ""),
            database=clickhouse.get("database", "default"),
            table=clickhouse.get("table", "data_breach_events_distributed"),
            secure=bool(clickhouse.get("secure", False)),
        ),
        processed_dir=_get_path(data, "processed_dir", "data/intranet_side/llm_pipeline/processed"),
        failed_dir=_get_path(data, "failed_dir", "data/intranet_side/llm_pipeline/failed"),
        internet_logs_dir=_get_path(data, "internet_logs_dir", "data/internet_side/logs"),
        intranet_logs_dir=_get_path(data, "intranet_logs_dir", "data/logs/intranet_side"),
    )
