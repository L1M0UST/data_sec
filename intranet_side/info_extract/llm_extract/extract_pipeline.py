from __future__ import annotations

import datetime as dt
import json
import shutil

from intranet_side.info_extract.config import PipelineConfig
from intranet_side.info_extract.llm_extract.db_writer import ClickHouseWriter
from intranet_side.info_extract.llm_extract.llm_client import request_qwen_json
from intranet_side.info_extract.llm_extract.markdown_loader import load_markdown_article
from intranet_side.info_extract.llm_extract.process_state import ProcessStateDB
from intranet_side.info_extract.llm_extract.text_clean import clean_text_for_llm, sanitize_string_list, sanitize_text_value
from intranet_side.info_extract.runtime_logging import build_stage_logger


REQUIRED_LLM_FIELDS = {
    "title",
    "company_name",
    "country",
    "region",
    "industry_sector",
    "records_count",
    "data_types",
    "attack_vector",
    "cve_ids",
    "severity",
    "ransom_involved",
    "tags",
    "breach_date",
    "attacker_name",
    "attacker_type",
    "attacker_aliases",
    "attacker_country",
    "attacker_region",
    "attacker_ips",
    "attacker_domains",
    "attacker_urls",
    "summary",
    "raw_content_zh",
}


def _validate_llm_result(result: object) -> dict:
    if not isinstance(result, dict):
        raise ValueError("大模型返回结果不是 JSON 对象")
    missing = sorted(REQUIRED_LLM_FIELDS - set(result.keys()))
    if missing:
        raise ValueError(f"大模型返回缺少必填字段: {', '.join(missing)}")
    array_fields = {
        "data_types",
        "cve_ids",
        "tags",
        "attacker_aliases",
        "attacker_ips",
        "attacker_domains",
        "attacker_urls",
    }
    for field in array_fields:
        value = result.get(field)
        if value is not None and not isinstance(value, (list, tuple, set, str)):
            raise ValueError(f"大模型返回字段类型不合法: {field}={type(value).__name__}")
    raw_content_zh = sanitize_text_value(result.get("raw_content_zh"), 120000)
    if len(raw_content_zh) < 20:
        raise ValueError("大模型返回的中文正文过短，无法入库")
    return result


def _build_row(article, result: dict) -> dict:
    return {
        "url": sanitize_text_value(article.url, 2000),
        "source": sanitize_text_value(article.source, 200),
        "site_id": sanitize_text_value(article.site_id, 200),
        "published_at": article.published_at,
        "crawled_at": article.crawled_at,
        "title": sanitize_text_value(result.get("title") or article.title, 2000),
        "company_name": result.get("company_name"),
        "country": result.get("country"),
        "region": result.get("region"),
        "industry_sector": result.get("industry_sector"),
        "records_count": result.get("records_count"),
        "data_types": sanitize_string_list(result.get("data_types"), item_max_len=100),
        "attack_vector": result.get("attack_vector"),
        "cve_ids": sanitize_string_list(result.get("cve_ids"), item_max_len=50),
        "severity": result.get("severity"),
        "ransom_involved": result.get("ransom_involved", 0),
        "attacker_name": result.get("attacker_name"),
        "attacker_type": result.get("attacker_type"),
        "attacker_aliases": sanitize_string_list(result.get("attacker_aliases"), item_max_len=200),
        "attacker_country": result.get("attacker_country"),
        "attacker_region": result.get("attacker_region"),
        "attacker_ips": sanitize_string_list(result.get("attacker_ips"), item_max_len=100),
        "attacker_domains": sanitize_string_list(result.get("attacker_domains"), item_max_len=255),
        "attacker_urls": sanitize_string_list(result.get("attacker_urls"), item_max_len=2000),
        "tags": sanitize_string_list(result.get("tags"), item_max_len=100),
        "breach_date": result.get("breach_date"),
        "raw_content": sanitize_text_value(result.get("raw_content_zh"), 120000),
    }


def extract_and_insert(config: PipelineConfig) -> int:
    inbox = config.ftp_remote.local_inbox_dir
    failed_dir = config.failed_dir
    logger = build_stage_logger(config.intranet_logs_dir, "llm_extract")
    state = ProcessStateDB(config.state_db_path.parent / "intranet_process_state.db")
    failed_dir.mkdir(parents=True, exist_ok=True)
    if not inbox.exists():
        logger.log(f"[抽取] 跳过执行：收件箱不存在，路径={inbox}")
        state.close()
        return 0

    writer = ClickHouseWriter(config.clickhouse)
    inserted = 0
    logger.log(f"[抽取] 开始执行，收件箱={inbox}，失败目录={failed_dir}，日志目录={config.intranet_logs_dir}")
    try:
        for path in sorted(inbox.rglob("*.md")):
            rel = path.relative_to(inbox)
            file_key = str(rel.as_posix())
            if state.has(file_key):
                logger.log(f"[抽取] 跳过重复文件，标识={file_key}，路径={path}")
                continue
            last_error: Exception | None = None
            for attempt in range(1, 3):
                try:
                    logger.log(f"[抽取] 开始处理文件，文件={path}，第{attempt}次尝试")
                    article = load_markdown_article(path)
                    cleaned_text = clean_text_for_llm(article.raw_content)[: config.llm.max_input_chars]
                    logger.log(f"[抽取] 已加载Markdown，标题={article.title}，URL={article.url}，正文长度={len(article.raw_content)}，送模长度={len(cleaned_text)}")
                    logger.log_block("[送大模型内容]", cleaned_text)
                    result = _validate_llm_result(request_qwen_json(config.llm, cleaned_text))
                    logger.log_block("[大模型返回内容]", json.dumps(result, ensure_ascii=False, indent=2))
                    row = _build_row(article, result)
                    insert_obj = writer.build_insert_object(row, row.get("raw_content") or "")
                    logger.log(f"[入库] 准备写入ClickHouse，库={writer.database}，表={writer.table}，URL={insert_obj.get('url')}")
                    logger.log_block("[入库对象]", json.dumps(insert_obj, ensure_ascii=False, indent=2, default=str))
                    writer.insert_event(row, row.get("raw_content") or "")
                    logger.log(f"[入库] 写入成功，库={writer.database}，表={writer.table}，URL={insert_obj.get('url')}")
                    if path.exists():
                        path.unlink()
                    state.upsert(file_key, str(path), dt.datetime.now().isoformat(timespec="seconds"), "success")
                    logger.log(f"[抽取] 文件处理成功并已删除原文件，文件={path}")
                    inserted += 1
                    last_error = None
                    break
                except Exception as exc:
                    last_error = exc
                    logger.log(f"[抽取] 第{attempt}次处理失败，文件={path}，错误={exc}")
                    if attempt < 2:
                        logger.log(f"[抽取] 准备重试一次，文件={path}")
            if last_error is not None:
                target = failed_dir / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                if path.exists():
                    shutil.move(str(path), str(target))
                state.upsert(file_key, str(path), dt.datetime.now().isoformat(timespec="seconds"), "failed")
                logger.log(f"[抽取] 文件两次处理失败，已移入失败目录，原文件={path}，目标文件={target}，错误={last_error}")
    finally:
        state.close()
    logger.log(f"[抽取] 执行完成，成功入库数量={inserted}")
    return inserted
