from __future__ import annotations

import sqlite3
from pathlib import Path


class ProcessStateDB:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(db_path))
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS processed_files (
              file_key TEXT PRIMARY KEY,
              source_path TEXT NOT NULL,
              processed_at TEXT NOT NULL,
              status TEXT NOT NULL
            )
            """
        )
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def has(self, file_key: str) -> bool:
        cur = self.conn.execute("SELECT 1 FROM processed_files WHERE file_key = ?", (file_key,))
        return cur.fetchone() is not None

    def upsert(self, file_key: str, source_path: str, processed_at: str, status: str) -> None:
        self.conn.execute(
            """
            INSERT INTO processed_files(file_key, source_path, processed_at, status)
            VALUES(?, ?, ?, ?)
            ON CONFLICT(file_key) DO UPDATE SET processed_at=excluded.processed_at, status=excluded.status
            """,
            (file_key, source_path, processed_at, status),
        )
        self.conn.commit()
