from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class SiteConfig:
    site_id: str
    name: str
    entry_urls: list[str]
    allowed_domains: list[str]
    discover: dict[str, Any]
    fetch: dict[str, Any]


@dataclass(frozen=True)
class AppConfig:
    output_dir: Path
    state_db: Path
    user_agent: str
    default_proxy: str | None
    sites: list[SiteConfig]


def load_config(config_path: Path) -> AppConfig:
    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    output_dir = Path(data.get("output_dir", "data"))
    state_db = Path(data.get("state_db", output_dir / "state" / "state.db"))
    user_agent = data.get("user_agent", "Mozilla/5.0")
    default_proxy = data.get("default_proxy")
    sites: list[SiteConfig] = []

    for s in data.get("sites", []):
        sites.append(
            SiteConfig(
                site_id=s["site_id"],
                name=s.get("name", s["site_id"]),
                entry_urls=list(s.get("entry_urls", [])),
                allowed_domains=list(s.get("allowed_domains", [])),
                discover=dict(s.get("discover", {})),
                fetch=dict(s.get("fetch", {})),
            )
        )

    return AppConfig(
        output_dir=output_dir,
        state_db=state_db,
        user_agent=user_agent,
        default_proxy=default_proxy,
        sites=sites,
    )
