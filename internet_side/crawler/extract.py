from __future__ import annotations

from dataclasses import dataclass

import trafilatura

from internet_side.crawler.normalize import clean_text


@dataclass(frozen=True)
class ExtractResult:
    title: str | None
    published_at: str | None
    text: str


def extract_text(html: str, url: str) -> ExtractResult:
    downloaded = trafilatura.extract(
        html,
        url=url,
        include_comments=False,
        include_tables=False,
        output_format="txt",
        favor_recall=True,
    )
    text = clean_text(downloaded or "")
    return ExtractResult(title=None, published_at=None, text=text)
