from __future__ import annotations

from datetime import datetime, timezone
import json
import re
from typing import Any

import requests

from intranet_side.info_extract.config import ClickHouseConfig
from intranet_side.info_extract.llm_extract.text_clean import sanitize_string_list, sanitize_text_value


INSERT_COLUMNS = [
    "url",
    "source",
    "site_id",
    "published_at",
    "crawled_at",
    "breach_date",
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
    "attacker_name",
    "attacker_type",
    "attacker_aliases",
    "attacker_country",
    "attacker_region",
    "attacker_ips",
    "attacker_domains",
    "attacker_urls",
    "raw_content",
    "tags",
]


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    v = value.strip()
    if v.endswith("Z"):
        v = v[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(v)
    except Exception:
        try:
            dt = datetime.strptime(value.strip(), "%Y-%m-%d %H:%M:%S")
        except Exception:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).replace(tzinfo=timezone.utc)


def _parse_uint64(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, float):
        return int(value) if value >= 0 else None
    if isinstance(value, str):
        digits = re.sub(r"[^\d]", "", value)
        if not digits:
            return None
        try:
            return int(digits)
        except Exception:
            return None
    return None


def _parse_date(value: str | None) -> datetime.date | None:
    dt = _parse_datetime(value)
    if dt is not None:
        return dt.date()
    if value:
        try:
            return datetime.fromisoformat(value).date()
        except Exception:
            return None
    return None


def sanitize_event_row(row: dict[str, Any], raw_content: str) -> list[Any]:
    published_at = _parse_datetime(row.get("published_at"))
    crawled_at = _parse_datetime(row.get("crawled_at")) or datetime.now(timezone.utc)
    breach_date = _parse_date(row.get("breach_date"))
    records_count = _parse_uint64(row.get("records_count"))
    ransom_involved = 1 if str(row.get("ransom_involved", 0)).strip().lower() in {"1", "true", "yes", "y"} else 0
    return [
        sanitize_text_value(row.get("url"), 2000),
        sanitize_text_value(row.get("source"), 200),
        sanitize_text_value(row.get("site_id"), 200),
        published_at,
        crawled_at,
        breach_date,
        sanitize_text_value(row.get("title"), 2000),
        sanitize_text_value(row.get("company_name"), 500),
        sanitize_text_value(row.get("country"), 100),
        sanitize_text_value(row.get("region"), 100),
        sanitize_text_value(row.get("industry_sector"), 200),
        records_count,
        sanitize_string_list(row.get("data_types"), item_max_len=100),
        sanitize_text_value(row.get("attack_vector"), 200),
        sanitize_string_list(row.get("cve_ids"), item_max_len=50),
        sanitize_text_value(row.get("severity"), 50),
        ransom_involved,
        sanitize_text_value(row.get("attacker_name"), 500),
        sanitize_text_value(row.get("attacker_type"), 100),
        sanitize_string_list(row.get("attacker_aliases"), item_max_len=200),
        sanitize_text_value(row.get("attacker_country"), 100),
        sanitize_text_value(row.get("attacker_region"), 100),
        sanitize_string_list(row.get("attacker_ips"), item_max_len=100),
        sanitize_string_list(row.get("attacker_domains"), item_max_len=255),
        sanitize_string_list(row.get("attacker_urls"), item_max_len=2000),
        sanitize_text_value(raw_content, 120000),
        sanitize_string_list(row.get("tags"), item_max_len=100),
    ]


def _make_json_safe(value: Any) -> Any:
    if isinstance(value, str):
        return value.encode("utf-8", errors="replace").decode("utf-8")
    if isinstance(value, list):
        return [_make_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(k): _make_json_safe(v) for k, v in value.items()}
    return value


class ClickHouseWriter:
    def __init__(self, config: ClickHouseConfig):
        scheme = "https" if config.secure else "http"
        self.base_url = f"{scheme}://{config.host}:{config.port}"
        self.username = config.username
        self.password = config.password
        table_name = config.table.strip()
        if "." in table_name:
            db_name, pure_table = table_name.split(".", 1)
            self.database = db_name.strip() or config.database
            self.table = pure_table.strip()
        else:
            self.database = config.database
            self.table = table_name

    def build_insert_object(self, row: dict[str, Any], raw_content: str) -> dict[str, Any]:
        sanitized = sanitize_event_row(row, raw_content)
        obj = dict(zip(INSERT_COLUMNS, sanitized))

        published_at = obj.get("published_at")
        if isinstance(published_at, datetime):
            obj["published_at"] = published_at.strftime("%Y-%m-%d %H:%M:%S")
        crawled_at = obj.get("crawled_at")
        if isinstance(crawled_at, datetime):
            obj["crawled_at"] = crawled_at.strftime("%Y-%m-%d %H:%M:%S")
        breach_date = obj.get("breach_date")
        if breach_date is not None:
            obj["breach_date"] = str(breach_date)
        return _make_json_safe(obj)

    def insert_event(self, row: dict[str, Any], raw_content: str) -> None:
        obj = self.build_insert_object(row, raw_content)

        query = f"INSERT INTO `{self.database}`.`{self.table}` ({', '.join(INSERT_COLUMNS)}) FORMAT JSONEachRow"
        data = json.dumps(obj, ensure_ascii=True) + "\n"

        params = {"database": self.database, "query": query}
        if self.username:
            params["user"] = self.username
        if self.password:
            params["password"] = self.password

        resp = requests.post(
            self.base_url,
            params=params,
            data=data,
            headers={"Content-Type": "text/plain; charset=utf-8"},
            timeout=30,
        )
        if not resp.ok:
            detail = resp.text.strip()
            raise RuntimeError(
                f"ClickHouse入库失败 status={resp.status_code} database={self.database} table={self.table} detail={detail}"
            )
