from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from pathlib import Path
import re

import httpx
from dateutil import tz

from internet_side.crawler.config import load_config
from internet_side.crawler.discover import (
    choose_discover_mode,
    discover_links_from_html,
    discover_links_from_rss_filtered,
)
from internet_side.crawler.extract import extract_text
from internet_side.crawler.fetcher import RateLimiter, build_client_any, fetch_text, get_rate_limit
from internet_side.crawler.normalize import canonicalize_url, stable_hash
from internet_side.crawler.state import StateDB
from internet_side.crawler.writer import Article, append_index, write_article


@dataclass
class SiteStats:
    site_id: str
    name: str
    entry_ok: int = 0
    entry_failed: int = 0
    discovered: int = 0
    skipped_seen: int = 0
    success: int = 0
    failed: int = 0
    fail_reasons: dict[str, int] = field(default_factory=dict)

    def add_reason(self, reason: str) -> None:
        self.fail_reasons[reason] = self.fail_reasons.get(reason, 0) + 1


def _exc_reason(e: Exception) -> str:
    if isinstance(e, httpx.HTTPStatusError):
        return f"http_{e.response.status_code}"
    resp = getattr(e, "response", None)
    status_code = getattr(resp, "status_code", None)
    if isinstance(status_code, int):
        return f"http_{status_code}"
    if isinstance(e, httpx.TimeoutException):
        return "timeout"
    msg = str(e).strip().lower()
    m = re.search(r"\b(4\d\d|5\d\d)\b", msg)
    if m:
        return f"http_{m.group(1)}"
    if "too short" in msg:
        return "too_short"
    return e.__class__.__name__


def run(
    config_path: Path,
    target_date: dt.date,
    today_only: bool,
    max_per_site: int,
    proxy_override: str | None = None,
    site_ids: set[str] | None = None,
    test_mode: bool = False,
) -> None:
    cfg = load_config(config_path)
    selected_sites = [site for site in cfg.sites if not site_ids or site.site_id in site_ids]
    if test_mode and not site_ids and selected_sites:
        selected_sites = selected_sites[:1]
    base_dir = cfg.output_dir
    base_dir.mkdir(parents=True, exist_ok=True)

    state = StateDB(cfg.state_db)
    day = target_date.isoformat()
    now_iso = dt.datetime.now(tz=tz.tzlocal()).isoformat(timespec="seconds")
    all_stats: list[SiteStats] = []
    logs_dir = base_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    summary_log_path = logs_dir / f"{day}_summary.log"
    summary_jsonl_path = logs_dir / f"{day}_summary.jsonl"

    def log_line(line: str) -> None:
        print(line, flush=True)
        with summary_log_path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")

    def log_json(obj: dict) -> None:
        import json

        with summary_jsonl_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")

    try:
        log_line(f"[crawl] start config={config_path} target_date={day} today_only={today_only} max_per_site={max_per_site} test_mode={test_mode}")
        log_line(f"[crawl] output_dir={base_dir} state_db={cfg.state_db}")
        log_line(f"[crawl] selected_sites={','.join([s.site_id for s in selected_sites]) or '-'}")
        for site in selected_sites:
            stats = SiteStats(site_id=site.site_id, name=site.name)
            all_stats.append(stats)
            fetch_cfg = site.fetch or {}
            extra_headers = dict(fetch_cfg.get("headers", {})) if isinstance(fetch_cfg.get("headers", {}), dict) else {}
            limiter = RateLimiter(per_sec=get_rate_limit(fetch_cfg))
            use_curl_cffi = bool(fetch_cfg.get("use_curl_cffi", False))
            proxy = proxy_override or fetch_cfg.get("proxy") or cfg.default_proxy
            effective_max = min(max_per_site, 3) if test_mode else max_per_site
            log_line(
                f"[crawl] site start site_id={site.site_id} name={site.name} discover_mode={choose_discover_mode(site.discover)} proxy={proxy or '-'} max_articles={effective_max}"
            )
            client = build_client_any(cfg.user_agent, extra_headers=extra_headers, use_curl_cffi=use_curl_cffi, proxy=proxy)

            try:
                all_links: list[str] = []
                mode = choose_discover_mode(site.discover)
                allow_re = site.discover.get("link_allow_regex")
                deny_re = site.discover.get("link_deny_regex")
                item_text_allow_re = site.discover.get("item_text_allow_regex")
                rss_use_summary = bool(site.discover.get("rss_use_summary", False))

                rss_items: list[dict] = []

                for entry in site.entry_urls:
                    entry = canonicalize_url(entry)
                    try:
                        log_line(f"[{site.site_id}] fetch entry={entry}")
                        entry_html = fetch_text(client, entry, limiter)
                        stats.entry_ok += 1
                        log_line(f"[{site.site_id}] entry fetched bytes={len(entry_html)} entry={entry}")
                        if mode == "rss":
                            links = discover_links_from_rss_filtered(
                                entry_html,
                                site.allowed_domains,
                                allow_re,
                                deny_re,
                                item_text_allow_re,
                            )
                            if rss_use_summary:
                                # parse rss items again to collect metadata for summary mode
                                from bs4 import BeautifulSoup

                                soup = BeautifulSoup(entry_html, "xml")
                                for item in soup.find_all(["item", "entry"]):
                                    link_tag = item.find("link")
                                    link = None
                                    if link_tag is not None:
                                        if link_tag.string:
                                            link = link_tag.string.strip()
                                        else:
                                            href = link_tag.get("href")
                                            if href:
                                                link = href.strip()
                                    if not link:
                                        continue
                                    link = canonicalize_url(link)
                                    if link not in links:
                                        continue

                                    title_tag = item.find("title")
                                    pub_tag = item.find("pubDate") or item.find("published") or item.find("updated")
                                    desc_tag = item.find("description") or item.find("summary")

                                    rss_items.append(
                                        {
                                            "url": link,
                                            "title": title_tag.get_text(" ", strip=True) if title_tag else None,
                                            "published_at": pub_tag.get_text(" ", strip=True) if pub_tag else None,
                                            "description": desc_tag.get_text(" ", strip=True) if desc_tag else None,
                                        }
                                    )
                        else:
                            links = discover_links_from_html(entry, entry_html, site.allowed_domains, allow_re, deny_re)
                        log_line(f"[{site.site_id}] entry discovered links={len(links)} entry={entry}")
                        all_links.extend(links)
                    except Exception as e:
                        stats.entry_failed += 1
                        reason = _exc_reason(e)
                        stats.add_reason("entry_" + reason)
                        log_line(f"[{site.site_id}] entry failed: {entry} reason={reason} err={e}")
                        log_json(
                            {
                                "ts": now_iso,
                                "type": "entry_failed",
                                "site_id": site.site_id,
                                "entry_url": entry,
                                "reason": reason,
                                "error": str(e),
                            }
                        )
                        continue

                # de-dup while preserving order
                seen = set()
                discovered = []
                for u in all_links:
                    if u in seen:
                        continue
                    seen.add(u)
                    discovered.append(u)

                stats.discovered = len(discovered)
                log_line(f"[{site.site_id}] discovered unique_links={len(discovered)}")

                count = 0
                rss_meta_by_url = {x["url"]: x for x in rss_items if x.get("url")}

                for url in discovered:
                    if count >= effective_max:
                        break

                    url_hash = stable_hash(site.site_id + "|" + url)
                    if state.has(url_hash):
                        stats.skipped_seen += 1
                        log_line(f"[{site.site_id}] skip duplicated url={url}")
                        continue

                    try:
                        log_line(f"[{site.site_id}] process url={url}")
                        if rss_use_summary and mode == "rss":
                            meta = rss_meta_by_url.get(url, {})
                            title = meta.get("title") or url
                            published_at = meta.get("published_at")
                            desc = meta.get("description") or ""
                            if not desc or len(desc) < 20:
                                raise RuntimeError("rss summary too short")
                            art = Article(
                                site_id=site.site_id,
                                source=site.name,
                                url=url,
                                title=title,
                                published_at=published_at,
                                crawled_at=now_iso,
                                content_text=desc,
                            )
                        else:
                            log_line(f"[{site.site_id}] fetch raw article url={url}")
                            html = fetch_text(client, url, limiter)
                            log_line(f"[{site.site_id}] raw article fetched bytes={len(html)} url={url}")
                            extracted = extract_text(html, url)
                            if not extracted.text or len(extracted.text) < 200:
                                raise RuntimeError("extracted text too short")

                            art = Article(
                                site_id=site.site_id,
                                source=site.name,
                                url=url,
                                title=extracted.title or url,
                                published_at=extracted.published_at,
                                crawled_at=now_iso,
                                content_text=extracted.text,
                            )
                        saved = write_article(base_dir, day, art)
                        append_index(base_dir, day, art, saved)
                        log_line(f"[{site.site_id}] saved article path={saved}")
                        state.upsert(url_hash, site.site_id, url, now_iso, "success")
                        stats.success += 1
                        count += 1
                    except Exception as e:
                        state.upsert(url_hash, site.site_id, url, now_iso, "failed")
                        stats.failed += 1
                        stats.add_reason(_exc_reason(e))
                        log_line(f"[{site.site_id}] article failed url={url} reason={_exc_reason(e)} err={e}")
                        log_json(
                            {
                                "ts": now_iso,
                                "type": "article_failed",
                                "site_id": site.site_id,
                                "url": url,
                                "reason": _exc_reason(e),
                                "error": str(e),
                            }
                        )
                        continue
                log_line(f"[crawl] site completed site_id={site.site_id} success={stats.success} skipped_seen={stats.skipped_seen} failed={stats.failed}")
            finally:
                client.close()
    finally:
        state.close()

    log_line("")
    log_line("=== Crawl Summary ===")
    for s in all_stats:
        reasons = ", ".join([f"{k}:{v}" for k, v in sorted(s.fail_reasons.items(), key=lambda kv: (-kv[1], kv[0]))])
        if not reasons:
            reasons = "-"
        line = (
            f"[{s.site_id}] {s.name} | entry_ok={s.entry_ok} entry_failed={s.entry_failed} "
            f"discovered={s.discovered} skipped_seen={s.skipped_seen} success={s.success} failed={s.failed} "
            f"reasons={reasons}"
        )
        log_line(line)
        log_json(
            {
                "ts": now_iso,
                "type": "site_summary",
                "site_id": s.site_id,
                "name": s.name,
                "entry_ok": s.entry_ok,
                "entry_failed": s.entry_failed,
                "discovered": s.discovered,
                "skipped_seen": s.skipped_seen,
                "success": s.success,
                "failed": s.failed,
                "reasons": s.fail_reasons,
            }
        )
