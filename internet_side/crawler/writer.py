from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from internet_side.crawler.normalize import clean_text, slugify


@dataclass
class Article:
    site_id: str
    source: str
    url: str
    title: str
    published_at: str | None
    crawled_at: str
    content_text: str


def write_article(base_dir: Path, day: str, article: Article) -> Path:
    out_dir = base_dir / "articles" / day / article.site_id
    out_dir.mkdir(parents=True, exist_ok=True)

    slug = slugify(article.title)
    path = out_dir / f"{slug}.md"

    front = {
        "title": article.title,
        "url": article.url,
        "source": article.source,
        "site_id": article.site_id,
        "published_at": article.published_at,
        "crawled_at": article.crawled_at,
    }

    body = clean_text(article.content_text)
    md = "---\n" + "\n".join([f"{k}: {json.dumps(v, ensure_ascii=False)}" for k, v in front.items()]) + "\n---\n\n" + body + "\n"
    path.write_text(md, encoding="utf-8")
    return path


def append_index(base_dir: Path, day: str, article: Article, saved_path: Path) -> None:
    idx_dir = base_dir / "index"
    idx_dir.mkdir(parents=True, exist_ok=True)
    idx_path = idx_dir / f"{day}.jsonl"
    record = asdict(article)
    record["saved_path"] = str(saved_path.as_posix())
    with idx_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
