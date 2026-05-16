from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from internet_side.crawler.normalize import canonicalize_url


def _domain_allowed(url: str, allowed_domains: list[str]) -> bool:
    if not allowed_domains:
        return True
    host = urlparse(url).netloc.lower()
    return any(host == d or host.endswith("." + d) for d in [x.lower() for x in allowed_domains])


def discover_links_from_html(base_url: str, html: str, allowed_domains: list[str], allow_re: str | None, deny_re: str | None) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    links: list[str] = []
    allow = re.compile(allow_re) if allow_re else None
    deny = re.compile(deny_re) if deny_re else None

    for a in soup.select("a[href]"):
        href = a.get("href")
        if not href:
            continue
        abs_url = urljoin(base_url, href)
        abs_url = canonicalize_url(abs_url)
        if not _domain_allowed(abs_url, allowed_domains):
            continue
        if deny and deny.search(abs_url):
            continue
        if allow and not allow.search(abs_url):
            continue
        links.append(abs_url)

    # keep order, de-dup
    seen = set()
    out = []
    for u in links:
        if u in seen:
            continue
        seen.add(u)
        out.append(u)
    return out


def discover_links_from_rss_filtered(
    xml_text: str,
    allowed_domains: list[str],
    allow_re: str | None,
    deny_re: str | None,
    item_text_allow_re: str | None,
) -> list[str]:
    if not item_text_allow_re:
        return discover_links_from_rss(xml_text, allowed_domains, allow_re, deny_re)

    soup = BeautifulSoup(xml_text, "xml")
    item_allow = re.compile(item_text_allow_re)
    allow = re.compile(allow_re) if allow_re else None
    deny = re.compile(deny_re) if deny_re else None

    links: list[str] = []
    for item in soup.find_all(["item", "entry"]):
        parts: list[str] = []
        t = item.find("title")
        if t and t.get_text():
            parts.append(t.get_text(" ", strip=True))
        for c in item.find_all("category"):
            if c.get_text():
                parts.append(c.get_text(" ", strip=True))
        d = item.find("description")
        if d and d.get_text():
            parts.append(d.get_text(" ", strip=True))

        item_text = "\n".join([p for p in parts if p])
        if item_text and not item_allow.search(item_text):
            continue

        link = None
        if item.find("link") is not None:
            if item.find("link").string:
                link = item.find("link").string.strip()
            else:
                href = item.find("link").get("href")
                if href:
                    link = href.strip()
        if not link:
            continue

        link = canonicalize_url(link)
        if not _domain_allowed(link, allowed_domains):
            continue
        if deny and deny.search(link):
            continue
        if allow and not allow.search(link):
            continue
        links.append(link)

    seen = set()
    out = []
    for u in links:
        if u in seen:
            continue
        seen.add(u)
        out.append(u)
    return out


def discover_links_from_rss(xml_text: str, allowed_domains: list[str], allow_re: str | None, deny_re: str | None) -> list[str]:
    soup = BeautifulSoup(xml_text, "xml")
    allow = re.compile(allow_re) if allow_re else None
    deny = re.compile(deny_re) if deny_re else None
    links: list[str] = []

    for item in soup.find_all(["item", "entry"]):
        link = None
        if item.find("link") is not None:
            # RSS: <link>url</link>
            if item.find("link").string:
                link = item.find("link").string.strip()
            else:
                # Atom: <link href="..."/>
                href = item.find("link").get("href")
                if href:
                    link = href.strip()
        if not link:
            continue
        link = canonicalize_url(link)
        if not _domain_allowed(link, allowed_domains):
            continue
        if deny and deny.search(link):
            continue
        if allow and not allow.search(link):
            continue
        links.append(link)

    seen = set()
    out = []
    for u in links:
        if u in seen:
            continue
        seen.add(u)
        out.append(u)
    return out


def choose_discover_mode(discover_cfg: dict) -> str:
    mode = str(discover_cfg.get("mode", "html")).lower()
    if mode in {"rss", "xml"}:
        return "rss"
    return "html"
