from __future__ import annotations

import datetime as dt
from pathlib import Path


class StageLogger:
    def __init__(self, log_file: Path):
        self.log_file = log_file
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

    def log(self, message: str) -> None:
        ts = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{ts}] {message}"
        print(line, flush=True)
        with self.log_file.open("a", encoding="utf-8") as f:
            f.write(line + "\n")

    def log_block(self, title: str, content: str) -> None:
        self.log(f"{title} 开始")
        if content:
            for line in content.splitlines():
                self.log(f"{title} | {line}")
        else:
            self.log(f"{title} | <空>")
        self.log(f"{title} 结束")


def build_stage_logger(log_dir: Path, stage_name: str) -> StageLogger:
    day = dt.date.today().isoformat()
    return StageLogger(log_dir / f"{day}_{stage_name}.log")
