from __future__ import annotations

import datetime as dt
from pathlib import Path

from internet_side.crawler.runner import run as crawl_run
from internet_side.crawler.sftp_upload.upload import upload_articles
from intranet_side.info_extract.config import load_pipeline_config
from intranet_side.info_extract.ftp_get.pull import pull_articles
from intranet_side.info_extract.llm_extract.extract_pipeline import extract_and_insert


def run_pipeline(
    config_path: Path,
    action: str,
    target_date: dt.date | None = None,
    max_per_site: int = 50,
    proxy: str | None = None,
    site_ids: set[str] | None = None,
    test_mode: bool = False,
) -> None:
    config = load_pipeline_config(config_path)
    print(f"[pipeline] start action={action} config={config_path} test_mode={test_mode} site_ids={site_ids or '-'}", flush=True)
    if action in {"crawl", "all"}:
        crawl_run(
            config_path=config.crawler_config_path,
            target_date=target_date or dt.date.today(),
            today_only=False,
            max_per_site=max_per_site,
            proxy_override=proxy,
            site_ids=site_ids,
            test_mode=test_mode,
        )
    if action in {"upload", "all"}:
        uploaded = upload_articles(config)
        print(f"[pipeline] uploaded={uploaded}", flush=True)
    if action in {"pull", "all"}:
        pulled = pull_articles(config)
        print(f"[pipeline] pulled={pulled}", flush=True)
    if action in {"extract", "all"}:
        inserted = extract_and_insert(config)
        print(f"[pipeline] inserted={inserted}", flush=True)
    print("[pipeline] completed", flush=True)
