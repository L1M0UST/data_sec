from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class LoadedArticle:
    path: Path
    title: str
    url: str
    source: str
    site_id: str
    published_at: str | None
    crawled_at: str
    raw_content: str


def load_markdown_article(path: Path) -> LoadedArticle:
    text = path.read_text(encoding="utf-8", errors="ignore")
    frontmatter = {}
    body = text
    if text.startswith("---\n"):
        try:
            _, rest = text.split("---\n", 1)
            front_text, body = rest.split("\n---\n", 1)
            frontmatter = yaml.safe_load(front_text) or {}
            if not isinstance(frontmatter, dict):
                frontmatter = {}
        except Exception:
            frontmatter = {}
            body = text
    return LoadedArticle(
        path=path,
        title=str(frontmatter.get("title") or ""),
        url=str(frontmatter.get("url") or ""),
        source=str(frontmatter.get("source") or ""),
        site_id=str(frontmatter.get("site_id") or ""),
        published_at=frontmatter.get("published_at"),
        crawled_at=str(frontmatter.get("crawled_at") or ""),
        raw_content=body.strip(),
    )
