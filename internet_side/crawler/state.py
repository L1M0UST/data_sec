from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SeenItem:
    site_id: str
    url: str
    url_hash: str
    status: str


class StateDB:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(db_path))
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS seen (
              url_hash TEXT PRIMARY KEY,
              site_id TEXT NOT NULL,
              url TEXT NOT NULL,
              first_seen_at TEXT NOT NULL,
              last_status TEXT NOT NULL
            )
            """
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_seen_site ON seen(site_id)"
        )
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def has(self, url_hash: str) -> bool:
        cur = self.conn.execute("SELECT 1 FROM seen WHERE url_hash = ?", (url_hash,))
        return cur.fetchone() is not None

    def upsert(self, url_hash: str, site_id: str, url: str, first_seen_at: str, last_status: str) -> None:
        self.conn.execute(
            """
            INSERT INTO seen(url_hash, site_id, url, first_seen_at, last_status)
            VALUES(?, ?, ?, ?, ?)
            ON CONFLICT(url_hash) DO UPDATE SET last_status=excluded.last_status
            """,
            (url_hash, site_id, url, first_seen_at, last_status),
        )
        self.conn.commit()
